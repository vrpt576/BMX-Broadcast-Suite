"""Server-owned, persistent and cancellable official-results playback."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import threading

from connector.models import (
    ActiveGraphic,
    CurrentResults,
    ResultsRollStart,
    ResultsRollState,
)
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_results_service import CurrentResultsService
from connector.services.event_service import EventService

logger = logging.getLogger(__name__)


class ResultsRollUnavailableError(LookupError):
    pass


class ResultsRollService:
    def __init__(
        self,
        current: CurrentMotoService,
        events: EventService,
        results: CurrentResultsService,
        state_file: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.current = current
        self.events = events
        self.results = results
        self.state_file = state_file
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._worker: threading.Thread | None = None
        self._catalog: list[CurrentResults] = []
        self._display_result: CurrentResults | None = None
        self._state = self._read_state()
        if self._state.active:
            self._state = self._state.model_copy(
                update={"paused": True, "next_change_at": None}
            )
            self._write_state()

    def start_worker(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._wake.clear()
            self._worker = threading.Thread(
                target=self._run,
                name="bbs-results-roll",
                daemon=True,
            )
            self._worker.start()

    def shutdown(self) -> None:
        self._wake.set()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=2)

    def status(self) -> ResultsRollState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def current_result(self, *, demo: bool = False) -> CurrentResults:
        with self._lock:
            if self._display_result is not None and not demo:
                return self._display_result.model_copy(deep=True)
        return self.results.get(demo=demo)

    def show_current(self) -> ResultsRollState:
        result = self.results.get()
        with self._lock:
            self.current.set_graphic(ActiveGraphic.RESULTS)
            self._catalog = [result]
            self._display_result = result.model_copy(
                update={"progress_index": 1, "progress_total": 1}
            )
            self._state = ResultsRollState(
                active=False,
                paused=False,
                interval_seconds=self._state.interval_seconds,
                motoboard_id=result.motoboard_id,
                event_name=result.event_name,
                current_result_index=0,
                current_result_moto=result.moto_number,
                total_available_results=1,
            )
            self._write_state()
            return self.status()

    def start(self, request: ResultsRollStart) -> ResultsRollState:
        selected = self.current.get()
        event = (
            self.events.by_motoboard(selected.motoboard_id)
            if selected.motoboard_id is not None
            else self.events.current()
        )
        catalog = self.results.catalog(
            event.motoboard_id,
            event_name=event.event_name,
        )
        if not catalog:
            raise ResultsRollUnavailableError(
                "No official final or overall results are available for this event."
            )
        index = 0
        if request.start_from == "current":
            exact = next(
                (
                    position
                    for position, result in enumerate(catalog)
                    if result.moto_number == selected.moto_number
                    and result.race_phase == selected.race_phase
                ),
                None,
            )
            if exact is None:
                phase_order = {
                    "round_1": 0,
                    "round_2": 1,
                    "round_3": 2,
                    "quarterfinal": 3,
                    "semifinal": 3,
                    "main": 3,
                    "overall": 3,
                }
                selected_key = (
                    phase_order[selected.race_phase.value],
                    selected.moto_number,
                )
                exact = next(
                    (
                        position
                        for position, result in enumerate(catalog)
                        if (
                            phase_order[result.race_phase.value],
                            result.moto_number,
                        )
                        > selected_key
                    ),
                    len(catalog) - 1,
                )
            index = exact

        now = self.clock()
        with self._lock:
            self.current.set_graphic(ActiveGraphic.RESULTS)
            self._catalog = catalog
            self._display_result = catalog[index]
            self._state = ResultsRollState(
                active=True,
                paused=False,
                interval_seconds=request.interval_seconds,
                motoboard_id=event.motoboard_id,
                event_name=event.event_name,
                current_result_index=index,
                current_result_moto=catalog[index].moto_number,
                total_available_results=len(catalog),
                started_at=now,
                next_change_at=now + timedelta(seconds=request.interval_seconds),
            )
            self._write_state()
        self.start_worker()
        return self.status()

    def pause(self) -> ResultsRollState:
        with self._lock:
            if self._state.active and not self._state.paused:
                self._state = self._state.model_copy(
                    update={"paused": True, "next_change_at": None}
                )
                self._write_state()
            return self.status()

    def pause_if_active(self) -> ResultsRollState:
        return self.pause()

    def resume(self) -> ResultsRollState:
        with self._lock:
            if not self._state.active:
                raise ResultsRollUnavailableError("The Results Roll is not active.")
            if not self._catalog:
                raise ResultsRollUnavailableError(
                    "Results must be loaded again before the roll can resume."
                )
            self._state = self._state.model_copy(
                update={
                    "paused": False,
                    "next_change_at": self.clock()
                    + timedelta(seconds=self._state.interval_seconds),
                }
            )
            self._write_state()
        self.start_worker()
        return self.status()

    def previous(self) -> ResultsRollState:
        return self._manual_step(-1)

    def next(self) -> ResultsRollState:
        return self._manual_step(1)

    def stop(self) -> ResultsRollState:
        with self._lock:
            self._state = self._state.model_copy(
                update={"active": False, "paused": False, "next_change_at": None}
            )
            self._write_state()
            return self.status()

    def tick(self, now: datetime | None = None) -> ResultsRollState:
        with self._lock:
            moment = now or self.clock()
            if (
                not self._state.active
                or self._state.paused
                or self._state.next_change_at is None
                or moment < self._state.next_change_at
            ):
                return self.status()
            self._step_locked(1, moment=moment, automatic=True)
            return self.status()

    def _manual_step(self, direction: int) -> ResultsRollState:
        with self._lock:
            if not self._catalog or self._state.current_result_index is None:
                raise ResultsRollUnavailableError("No Results Roll is loaded.")
            self._step_locked(direction, moment=self.clock(), automatic=False)
            return self.status()

    def _step_locked(
        self,
        direction: int,
        *,
        moment: datetime,
        automatic: bool,
    ) -> None:
        assert self._state.current_result_index is not None
        target = self._state.current_result_index + direction
        target = max(0, min(target, len(self._catalog) - 1))
        at_end = direction > 0 and target == self._state.current_result_index
        reached_end = direction > 0 and target == len(self._catalog) - 1
        update: dict[str, object] = {
            "current_result_index": target,
            "current_result_moto": self._catalog[target].moto_number,
        }
        self._display_result = self._catalog[target]
        if automatic and (at_end or reached_end):
            update.update(active=False, paused=False, next_change_at=None)
        elif self._state.active and not self._state.paused:
            update["next_change_at"] = moment + timedelta(
                seconds=self._state.interval_seconds
            )
        self._state = self._state.model_copy(update=update)
        self._write_state()

    def _run(self) -> None:
        while not self._wake.wait(0.25):
            try:
                self.tick()
            except Exception:
                logger.exception("Results Roll timer failed; pausing playback.")
                self.pause()

    def _read_state(self) -> ResultsRollState:
        try:
            return ResultsRollState.model_validate_json(
                self.state_file.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return ResultsRollState()

    def _write_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.state_file)

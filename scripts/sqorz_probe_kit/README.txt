SQORZ PROBE - README
=====================

WHAT IS THIS?

A small, one-time check to see whether the timing software you use at the
track (Sqorz) can be reached over your local network, and to save a copy of
what it says back. That's it -- it doesn't install anything, doesn't change
anything, and doesn't need the internet.

It was sent to you by someone building a broadcast/overlay tool for another
track, who wants to make sure it works correctly with your particular Sqorz
setup before showing up in person. Running this ahead of time means it can
be tested properly instead of guessed at while standing at your scoring
table.


IS THIS SAFE TO RUN?

Yes. A few specifics:

  - It is READ-ONLY. It only asks Sqorz questions ("what classes are
    running", "what are the current times") -- it never changes, deletes,
    or adds anything, in Sqorz or anywhere else.
  - It only talks to Sqorz over YOUR network. It does not use the internet,
    and it does not send anything anywhere by itself.
  - It only collects the same kind of information already shown on Sqorz's
    own public results pages for the event -- class names, round numbers,
    plate numbers, rider names, and times. It does not collect anything
    about your members beyond that: no addresses, phone numbers,
    birthdates, or payment information.
  - You look at everything it saved before you send it anywhere. Nothing
    is sent automatically.


HOW TO RUN IT

1. Unzip this folder somewhere you can find it (like your Desktop) if you
   haven't already.

2. Make sure you're on the same WiFi/network as the Sqorz scoring
   computer.

3. Double-click "Run Sqorz Probe.bat".

4. A black window will open and ask one or two simple questions:
     - Do you know the scoring computer's IP address? If not, just press
       Enter and it will look for it on your network automatically.
   Answer, and it will do the rest by itself -- usually a few seconds.

5. When it's done, it will tell you whether it found the scoring computer
   and how many of its questions got answered. It will also create a new
   .zip file in this same folder.

6. Email that new .zip file (NOT this whole folder, just the new file it
   just created) to the address the program prints on screen. If you're
   not sure which file that is, look for the newest one -- its name starts
   with "sqorz-probe-" followed by today's date and time.

7. Press any key to close the window. You're done.


WHAT IF SOMETHING GOES WRONG?

  - "This computer does not appear to have Python installed" -- see the
    on-screen instructions; you'll need to install Python once from
    python.org (free, a couple of minutes), then try again.
  - It says it couldn't find anything on the network -- double check
    you're on the same WiFi as the scoring computer, and that Sqorz is
    actually running. It still creates a .zip file either way; you can
    send that too, since even "nothing answered" is useful information.
  - Anything else looks wrong -- don't worry about fixing it. Just send
    whatever .zip file it created (or a screenshot of the window) to the
    email address above, and it'll be sorted out from there.


THAT'S EVERYTHING

One program, one question or two, one file to send back. Thank you for
taking the few minutes to run this -- it makes the actual visit much
smoother.

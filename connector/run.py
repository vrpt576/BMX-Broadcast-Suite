"""Config-aware BBS launcher."""
import uvicorn
from connector.config import get_settings

if __name__ == '__main__':
    s=get_settings()
    uvicorn.run('connector.main:app',host=s.app_host,port=s.app_port,log_level=s.log_level.lower())

from json import loads
import subprocess

from .models.mining_info import MiningInfo

class Client:
    def __init__(self, datadir: str):
        self.datadir = datadir
    
    def _make_call(self, cmd: str):
        return subprocess.getoutput(f"sudo bitcoin-cli --datadir={self.datadir} {cmd}")

    def get_mining_info(self) -> MiningInfo:
        return MiningInfo(**loads(self._make_call("getmininginfo")))
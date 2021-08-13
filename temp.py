from requests import session

from .errors import WorkerTimedOutError
from .core import CPUClient, printTS


class TempCPUWorker:
    def __init__(self,
            url: str = "http://crawlingathome.duckdns.org/",
            nickname: str = "anonymous") -> None:
        
        if url[-1] != "/":
            url += "/"
        
        self.s = session()
        self.url = url
        self.nickname = nickname
        
        self.completed = 0
        
        self._c = CPUClient(self.url, self.nickname)
        self.upload_address = self._c.upload_address
        
        self.log("Waiting for new job...")
        
    
    def log(self, msg: str) -> None:
        try:
            self._c.log(f"{msg} | Completed: {self.completed:,}", noprint=True)
        except WorkerTimedOutError:
            self._c = CPUClient(self.url, self.nickname)
            self.log(msg)
    
    
    def jobCount(self) -> int:
        return self._c.jobCount()
    
    
    def downloadShard(self, path="") -> None:
        print(f"{printTS()} downloading shard...")
        self.log("Downloading shard")

        with self.s.get(self.shard, stream=True) as r:
            r.raise_for_status()
            with open(path + "temp.gz", 'w+b') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)
            
        with gzip.open(path + 'temp.gz', 'rb') as f_in:
            with open(path + 'shard.wat', 'w+b') as f_out:
                shutil.copyfileobj(f_in, f_out)
            
        sleep(1) # Causes errors otherwise?
        os.remove(path + "temp.gz")

        self.log("Downloaded shard")
        print(f"{printTS()} finished downloading shard")
    
    
    def updateUploadServer(self) -> None:
        try:
            self._c.updateUploadServer()
            self.upload_address = self._c.upload_address
        except WorkerTimedOutError:
            self._c = CPUClient(self.url, self.nickname)
            self.updateUploadServer()
    
    
    def newJob(self) -> None:
        while True:
            wat = self.s.get(self.url + "custom/get-cpu-wat").text
            if not "http" in wat:
                print("[crawling@home] something went wrong when finding a job, breaking loop...")
                self.log("Crashed.")
                break
            
            # verify
            r = self.s.post(self.url + "custom/lookup-wat", json={
                "url": wat
            }).json()
            
            if r["status"] != "success":
                continue
            else:
                shards = r["shards"]
                if len(shards) < 2:
                    continue
                else:
                    self.shards = shards
                    self.wat = wat
                    self.log("Recieved new jobs.")
    
    
    def completeJob(self, urls: dict) -> None:
        r = self.s.post(self.url + "custom/markasdone-cpu", json={
            "urls": urls,
            "shards": [shard[0] for shard in self.shards],
            "nickname": self.nickname
        }).json()
        
        if r["status"] == "success":
            self.completed += r["completed"]
        
        self.log("Marked jobs as done.")
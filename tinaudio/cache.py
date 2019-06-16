from .shared import *


class ICache(object):
    """
    Directory tree in-memory cache
    """

    def __init__(self, path: str) -> None:
        """
        Cache constructor

        Arguments:
            path {str} -- Cache root directory

        Raises:
            Exception: If the directory argument is not absolute
        """
        if path[0] != '/':
            self.tracktunes = []
            raise Exception('path MUST be absolute')
        self.path = path
        while self.path[-1] == '/':
            self.path = self.path[:-1]
        self.index = []
        self.files = {}
        self.dirs = {}
        self.timecache = {}
        # walk, walk, walk
        for (xpath, xdirs, xfiles) in os.walk(self.path, topdown=True):
            relative_path = xpath[len(self.path) + 1:]
            self.index.append(relative_path)
            # store files
            xfiles.sort()
            tmpfiles = []
            # store dirs
            xdirs.sort()
            self.dirs[relative_path] = xdirs
            for f in xfiles:
                relative_file = os.path.join(relative_path, f)
                absolute_file = os.path.join(self.path, relative_file)
                if os.path.isfile(absolute_file):
                    self.timecache[relative_file] = os.path.getmtime(absolute_file)
                    tmpfiles.append(f)
            self.files[relative_path] = tmpfiles
        self.index.sort()

    def get(self, relative_path: str) -> Tuple[List[str], List[str]]:
        """
        Subdirectory and file entries for a given key/directory

        Arguments:
            relative_path {str} -- Key/directory relative to cache root

        Returns:
            (List(str), List(str)) -- Directories, Files
        """
        return (self.dirs[relative_path], self.files[relative_path])

    def getmtime(self, relative_file: str) -> float:
        """
        File modification time

        Arguments:
            relative_file {str} -- Key/file relative to cache root

        Returns:
            float -- Modification time
        """
        return self.timecache[relative_file]

    def getindex(self) -> List[str]:
        """
        Directory index (flattened) in cache

        Returns:
            List[str] -- Directories
        """
        return self.index

    def getroot(self) -> str:
        """
        Cache's root directory

        Returns:
            str -- Directory
        """
        return self.path

    def flatten(self) -> List[str]:
        """
        Lists all files in cache (flattened)

        Returns:
            List[str] -- Files
        """
        flat = []
        for k in self.index:
            (dirs, files) = self.get(k)
            for i in range(0, len(files)):
                flat.append(os.path.join(k, files[i]))
        return flat

    def getleafs(self) -> List[str]:
        """
        (Sub)directories with no directories/files within

        Returns:
            List[str] -- Directories
        """
        leafs = []
        for k in self.index:
            (dirs, files) = self.get(k)
            if len(files) > 0:
                leafs.append(k)
        leafs.sort()
        return leafs

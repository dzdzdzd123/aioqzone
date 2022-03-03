import asyncio
from collections import defaultdict
from functools import partial
from typing import Any, Coroutine


class ExecJS:
    def __init__(self, node: str = "node", *, js: str | None = None):
        self.js = js
        self.que = []
        self.node = node
        assert self.version() is not None, f"`{self.node}` is not installed."

    @staticmethod
    def callstr(func, *args, asis: bool = False) -> str:
        tostr = {bool: lambda i: ["false", "true"][i]}
        tostr = defaultdict(lambda: repr, tostr)
        quoted = (repr(i) if asis else tostr[type(i)](i) for i in args)
        return f'{func}({",".join(quoted)})'

    def addfunc(self, func: str, *args):
        self.que.append((func, *args))

    async def _exec(self, js: str):
        p = await asyncio.subprocess.create_subprocess_exec(
            self.node,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await p.communicate(js.encode())
        if stderr:
            raise RuntimeError(stderr.decode())
        return stdout.decode()

    def __call__(self, func: str, *args, asis: bool = False) -> Coroutine[Any, Any, str]:
        js = self.js
        assert js is not None
        for i in self.que:
            js += self.callstr(*i, asis=asis)
            js += ";"
        self.que.clear()
        js += f"\nconsole.log({self.callstr(func, *args, asis=asis)});process.exit();"
        return self._exec(js)

    def get(self, prop: str):
        assert self.js is not None
        js = self.js + f"\nconsole.log({prop});process.exit();"
        return self._exec(js)

    def bind(self, func: str, new: bool = True):
        n = ExecJS(self.node, js=self.js) if new else self
        return partial(n.__call__, func)

    def version(self):
        import subprocess

        try:
            p = subprocess.Popen(
                [self.node, "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            return
        stdout, stderr = p.communicate()
        if stderr:
            raise RuntimeError(stderr.decode())
        return stdout.decode()

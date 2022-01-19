import asyncio
import re
from http.cookies import SimpleCookie
from random import random
from typing import Awaitable, Callable

from ..base import LoginBase
from ..constants import StatusCode
from ..encrypt import hash33
from ..exception import UserBreak
from ..utils import raise_for_status

SHOW_QR = 'https://ssl.ptlogin2.qq.com/ptqrshow'
XLOGIN_URL = 'https://xui.ptlogin2.qq.com/cgi-bin/xlogin'
POLL_QR = 'https://ssl.ptlogin2.qq.com/ptqrlogin'
LOGIN_URL = 'https://ptlogin2.qzone.qq.com/check_sig'


class QRLogin(LoginBase):
    async def show(self):
        data = {
            'appid': self.app.appid,
            'e': 2,
            'l': 'M',
            's': 3,
            'd': 72,
            'v': 4,
            't': random(),
            'daid': self.app.daid,
            'pt_3rd_aid': 0,
        }
        async with self.session.get(SHOW_QR, params=data, ssl=self.ssl) as r:
            r.raise_for_status()
            self.qrsig = r.cookies['qrsig'].value
            return await r.content.read()

    async def pollStat(self):
        """poll status of the qr

        Raises:
            HTTPError: if response code != 200

        Returns:
            list: (code, ?, url, ?, msg, my_name)
        """
        data = {
            'u1': self.proxy.s_url,
            'ptqrtoken': hash33(self.qrsig),
            'ptredirect': 0,
            'h': 1,
            't': 1,
            'g': 1,
            'from_ui': 1,
            'ptlang': 2052,
        # 'action': 3-2-1626611307380,
        # 'js_ver': 21071516,
            'js_type': 1,
            'login_sig': "",
            'pt_uistyle': 40,
            'aid': self.app.appid,
            'daid': self.app.daid,
        # 'ptdrvs': 'JIkvP2N0eJUzU3Owd7jOvAkvMctuVfODUMSPltXYZwCLh8aJ2y2hdSyFLGxMaH1U',
        # 'sid': 6703626068650368611,
            'has_onekey': 1,
        }
        async with self.session.get(POLL_QR, params=data, ssl=self.ssl) as r:
            r.raise_for_status()
            r = re.findall(r"'(.*?)'[,\)]", await r.text())
            r[0] = int(r[0])
            if r[0] == 0: self.login_url = r[2]
            return r

    async def login(self):
        async with self.session.get(self.login_url, allow_redirects=False, ssl=self.ssl) as r:
            raise_for_status(r, 302)
            return r.cookies

    async def loop(
        self,
        send_callback: Callable[[bytes], Awaitable[None]],
        expire_callback: Callable[[bytes], Awaitable[None]] = None,
        refresh_time: int = 6,
        polling_freq: float = 3,
    ) -> asyncio.Future[SimpleCookie]:
        expire_callback = expire_callback or send_callback

        async def innerloop():
            assert expire_callback
            try:
                for i in range(refresh_time):
                    send = expire_callback if i else send_callback
                    await send(await self.show())
                    # future.set_exception(UserBreak)
                    while True:
                        await asyncio.sleep(polling_freq)
                        stat = await self.pollStat()
                        if stat[0] == StatusCode.Expired: break
                        if stat[0] == StatusCode.Authenticated:
                            return await self.login()
            except (KeyboardInterrupt, asyncio.CancelledError):
                raise UserBreak
            raise TimeoutError

        f = asyncio.Future()
        expire_callback = expire_callback or send_callback
        return asyncio.ensure_future(innerloop())

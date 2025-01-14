from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from qqqr.constant import QzoneAppid, QzoneProxy, captcha_status_description
from qqqr.up import UpWebLogin
from qqqr.up.captcha import Captcha, CollectEnv, TcaptchaSession
from qqqr.up.captcha.jigsaw import imitate_drag
from qqqr.up.captcha.vm import DecryptTDC

if TYPE_CHECKING:
    from test.conftest import test_env

    from qqqr.utils.net import ClientAdapter

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def captcha(client: ClientAdapter, env: test_env):
    login = UpWebLogin(client, QzoneAppid, QzoneProxy, env.uin, env.pwd.get_secret_value())
    upsess = await login.new()
    await login.check(upsess)
    captcha = login.captcha(upsess.check_rst.session)
    yield captcha


@pytest_asyncio.fixture(scope="class")
async def sess(captcha: Captcha):
    sess = await captcha.new()
    await captcha.get_tdc(sess)
    yield sess


class TestCaptcha:
    async def test_windowconf(self, sess: TcaptchaSession):
        assert sess.conf

    async def test_match_md5(self, sess: TcaptchaSession):
        sess.solve_workload()
        ans = sess.pow_ans
        assert 0 < ans <= 3e5
        assert sess.duration >= 50, f"{ans}, {sess.duration}"
        sess.solve_workload()
        assert ans == sess.pow_ans, f"{ans} != {sess.pow_ans}"

    async def test_puzzle(self, captcha: Captcha, sess: TcaptchaSession):
        await captcha.get_captcha_problem(sess)
        captcha.solve_captcha(sess)
        assert sess.jig_ans[0]
        assert sess.jig_ans[1]

    async def test_verify(self, captcha: Captcha):
        r = await captcha.verify()
        if r.code == 0:
            assert r.verifycode
            assert r.ticket
        else:
            pytest.xfail(captcha_status_description[r.code])


@pytest_asyncio.fixture(scope="class")
async def vm(captcha: Captcha, sess: TcaptchaSession):
    await captcha.get_tdc(sess)
    yield sess.tdc


class TestVM:
    async def testGetInfo(self, vm: CollectEnv):
        d = await vm.get_info()
        assert d
        assert d["info"]

    async def testCollectData(self, vm: CollectEnv):
        xs, ys = imitate_drag(21, 230, 50)
        vm.run.append("async function main(){await simulate_slide(%s, %s)}" % (str(xs), str(ys)))
        vm.add_run("main")
        d = await vm.get_data()
        assert d
        assert len(d) > 200

    async def testGetCookie(self, vm: CollectEnv):
        cookie = await vm.get_cookie()
        assert "TDC_itoken" in cookie


@pytest.mark.skip("this test should be called manually")
async def test_decrypt(vm: CollectEnv, captcha: Captcha, sess: TcaptchaSession):
    xs, ys = imitate_drag(21, 230, 50)
    vm.run.append("async function main(){await simulate_slide(%s, %s)}" % (str(xs), str(ys)))
    vm.add_run("main")
    collect = await vm.get_data()

    await captcha.get_tdc(sess, cls=DecryptTDC)
    decrypt = await DecryptTDC.decrypt(sess.tdc, collect)  # type: ignore
    print(decrypt)

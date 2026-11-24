"""Owned real-application server; test identity headers only, no security bypass."""
import os
from pathlib import Path
import sys
import threading

import uvicorn

from backend.tests.support import PROJECT_ROOT

root=Path(os.environ['PLACEPRO_TEST_STORAGE_ROOT']).resolve()
run_id=os.environ['PLACEPRO_TEST_RUN_ID'].encode('ascii')
for key in ('PLACEPRO_PROFILES_DIR','PLACEPRO_ASSESSMENTS_DIR','PLACEPRO_COMPANIES_DB','PLACEPRO_AUTH_DB'):
    path=Path(os.environ[key]).resolve()
    if not path.is_relative_to(root) or path.is_relative_to(PROJECT_ROOT/'data'):
        raise RuntimeError('Refusing non-isolated production-application validation.')

from backend.app.main import app as application  # Storage/config bound before import.


async def app(scope,receive,send):
    async def identify(message):
        if message['type']=='http.response.start':
            message=dict(message)
            message['headers']=list(message.get('headers',[]))+[
                (b'x-placepro-test-run-id',run_id),(b'x-placepro-test-process-id',str(os.getpid()).encode('ascii'))]
        await send(message)
    await application(scope,receive,identify)


if __name__=='__main__':
    config=uvicorn.Config(app,host='127.0.0.1',port=int(sys.argv[1]),proxy_headers=False,
                          ssl_keyfile=sys.argv[2] if len(sys.argv)>2 else None,
                          ssl_certfile=sys.argv[3] if len(sys.argv)>3 else None)
    server=uvicorn.Server(config)
    def stop_on_stdin():
        if sys.stdin.readline().strip()=='stop':
            server.should_exit=True
    threading.Thread(target=stop_on_stdin,daemon=True).start()
    server.run()

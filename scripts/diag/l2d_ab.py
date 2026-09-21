# -*- coding: utf-8 -*-
"""l2d_ab.py — 用真实运行时对同一模型的「旧 motion vs 新 motion」做渲染级 A/B。

做法：在 Output/Live2D/_ab/<model>/{old,new}/ 里用硬链接复用 moc3/贴图/physics，
model3.json 复制，motion/ 分别指向旧产物与新产物；然后在画廊页面里覆写
skin.live2d 路径加载，比较同一动作下的画面差异与参数轨迹。

用法: PYTHONIOENCODING=utf-8 py -3 scripts/diag/l2d_ab.py <model> [--motion idle]
      不给 --motion 时依次跑 idle / touch_head / main_1。
输出: .diag/l2d_ab_shots/<model>_<side>_<motion>.png + 终端报告
结束后可安全删除 Output/Live2D/_ab（仅本脚本生成的硬链接壳目录）。
"""
import sys, os, json, time, base64, shutil, subprocess, urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9336
SRV_PORT = 8791
DEBUG_DIR = os.path.join(ROOT, '.diag', 'chrome_l2d_ab')
SHOTS = os.path.join(ROOT, '.diag', 'l2d_ab_shots')
AB = os.path.join(ROOT, 'Output', 'Live2D', '_ab')
OLD_ROOT = os.path.join(ROOT, 'Output', 'Live2D')
NEW_ROOT = os.path.join(ROOT, '.diag', 'l2d_new')
os.makedirs(SHOTS, exist_ok=True)

args = [a for a in sys.argv[1:] if not a.startswith('--')]
MODELS = args[:1] or ['lingbo', 'aerbien_3']
MOTIONS = ([sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--motion']
           or ['idle', 'touch_head', 'main_1'])


def link_or_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isfile(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build_ab(model):
    """搭出 _ab/<model>/{old,new} 两个可加载目录。"""
    src_any = os.path.join(OLD_ROOT, model)
    out = {}
    for side, mroot in (('old', OLD_ROOT), ('new', NEW_ROOT)):
        d = os.path.join(AB, model, side)
        mdir = os.path.join(d, 'motion')
        os.makedirs(mdir, exist_ok=True)
        for fn in os.listdir(src_any):
            if fn.endswith(('.moc3', '.physics3.json', '.model3.json')) or fn.endswith('.png'):
                link_or_copy(os.path.join(src_any, fn), os.path.join(d, fn))
        src_motion = os.path.join(mroot, model, 'motion')
        n = 0
        if os.path.isdir(src_motion):
            for fn in os.listdir(src_motion):
                if fn.endswith('.motion3.json'):
                    link_or_copy(os.path.join(src_motion, fn), os.path.join(mdir, fn))
                    n += 1
        out[side] = n
    return out


def kill_stale_chrome(user_data_dir):
    """只杀命令行里带本脚本 --user-data-dir 的残留 chrome，绝不按进程名全杀（会误杀用户浏览器）。"""
    ps = ("$ErrorActionPreference='SilentlyContinue';"
          "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
          "Where-Object { $_.CommandLine -like '*%s*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % user_data_dir)
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)


def main():
    for m in MODELS:
        print(f'[*] 搭建 A/B: {m} -> {build_ab(m)}')

    srv = subprocess.Popen(
        [sys.executable, '-m', 'http.server', str(SRV_PORT),
         '-b', '127.0.0.1', '-d', os.path.join(ROOT, 'Output')],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    kill_stale_chrome(DEBUG_DIR)
    url = f'http://127.0.0.1:{SRV_PORT}/gallery_v2/index.html'
    for _ in range(40):                      # 等 http.server 真的绑上端口，否则 Chrome 拿到错误页
        try:
            if urllib.request.urlopen(url, timeout=2).status == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError('本地服务器未就绪 ' + url)

    proc = subprocess.Popen([
        CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
        '--remote-allow-origins=*', f'--user-data-dir={DEBUG_DIR}',
        '--no-first-run', '--no-default-browser-check',
        '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
        '--use-angle=swiftshader', '--window-size=900,900',
        url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait_ws():
        for _ in range(60):
            try:
                for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
                    if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl'):
                        return t['webSocketDebuggerUrl']
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError('CDP 未就绪')

    import websocket
    ws = websocket.create_connection(wait_ws(), timeout=90)
    _id = 0

    def cmd(method, params=None):
        nonlocal _id
        _id += 1
        ws.send(json.dumps({'id': _id, 'method': method, 'params': params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == _id:
                if 'error' in m:
                    raise RuntimeError(json.dumps(m['error'])[:200])
                return m.get('result', {})

    def ev(expr, awaitp=False):
        r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': awaitp})
        if r.get('exceptionDetails'):
            return 'EVALERR ' + str(r['exceptionDetails'].get('exception', {}).get('description'))[:200]
        return r.get('result', {}).get('value')

    def load(model, side):
        js = f"""(async () => {{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          let ship=null, sk=null;
          for (const s of GALLERY.ships) {{ const k=s.skins.find(x=>x.key==={json.dumps(model)});
            if(k&&s.live2dSkins.includes({json.dumps(model)})){{ship=s;sk=k;break;}} }}
          if(!sk) return JSON.stringify({{skip:'皮肤里没有 '+{json.dumps(model)}+' 的 Live2D'}});
          openShip(ship); setSkin(sk); buildSkinList(ship);
          sk.live2d = 'Live2D/_ab/{model}/{side}';
          sk.live2dBase = {json.dumps(model)};
          tab='live2d'; renderView();
          await t(9000);
          const app=l2State&&l2State.app; if(!app) return JSON.stringify({{fail:'无 l2State', note:(document.querySelector('.note')||{{}}).textContent||''}});
          const m0=app.stage.children[0]; if(!m0) return JSON.stringify({{fail:'无模型'}});
          window.__m=m0; window.__app=app;
          return JSON.stringify({{ok:true, fitK:+m0.scale.x.toFixed(5), natW:Math.round(m0.internalModel.width),
            natH:Math.round(m0.internalModel.height), groups:Object.keys(m0.internalModel.motionManager.definitions||{{}}).length}});
        }})()"""
        return ev(js, awaitp=True)

    def play_and_probe(motion, samples=6, step=280):
        """切到该动作，采样画面哈希 + 关键参数轨迹。"""
        js = f"""(async () => {{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const m=window.__m; if(!m) return JSON.stringify({{fail:'no model'}});
          const mm=m.internalModel.motionManager;
          if(!(mm.definitions||{{}})[{json.dumps(motion)}]) return JSON.stringify({{skip:'无动作 '+{json.dumps(motion)}}});
          mm.startMotion({json.dumps(motion)},0,PIXI.live2d.MotionPriority.FORCE);
          await t(1600);
          const core=m.internalModel.coreModel;
          const ids=['ParamAngleX','ParamAngleY','ParamEyeLOpen','ParamMouthOpenY','ParamBreath'];
          const parts=[]; try {{ for(const q of (core.parts||[])) {{ if(q&&q.id) parts.push(q.id); }} }} catch(e) {{}}
          parts.length=Math.min(parts.length,6);
          const traces={{}}; ids.concat(parts.map(x=>'@'+x)).forEach(i=>traces[i]=[]);
          const hashes=[]; const app=window.__app;
          for (let i=0;i<{samples};i++) {{
            /* 无头 rAF 被节流：不手动推进 ticker + render，帧哈希与参数轨迹都会假阴性 */
            try {{ PIXI.Ticker.shared.tick(performance.now()); }} catch(e) {{}}
            try {{ app.render(); }} catch(e) {{}}
            const c=document.createElement('canvas'); c.width=180; c.height=180;
            const g=c.getContext('2d'); g.drawImage(document.querySelector('#l2wrap canvas'),0,0,180,180);
            hashes.push(c.toDataURL().slice(-16));
            ids.forEach(id=>{{ try {{ const v=core.getParameterValueById(id); traces[id].push(v==null?null:+v.toFixed(3)); }} catch(e){{ traces[id].push(null); }} }});
            parts.forEach(id=>{{ try {{ const v=core.getPartOpacityById(id); traces['@'+id].push(v==null?null:+v.toFixed(3)); }} catch(e){{ traces['@'+id].push(null); }} }});
            await t({step});
          }}
          const uniq=new Set(hashes).size;
          const moved=Object.keys(traces).filter(id=>{{const a=traces[id].filter(v=>typeof v==='number'); return a.length>1 && Math.max(...a)-Math.min(...a) > 1e-4;}});
          return JSON.stringify({{uniqFrames:uniq, frames:hashes.length, movedParams:moved, traces,
            curGroup:(mm.state&&mm.state.currentGroup)||null}});
        }})()"""
        return ev(js, awaitp=True)

    cmd('Page.enable'); cmd('Runtime.enable')
    for _ in range(60):
        if ev("typeof GALLERY!=='undefined'") is True:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError('GALLERY 未就绪: ' + str(ev('JSON.stringify([document.title,location.href,(document.body||{}).innerText||""].slice(0,2))'))[:300])

    def shot(name):
        r = cmd('Page.captureScreenshot', {'format': 'png'})
        open(os.path.join(SHOTS, name + '.png'), 'wb').write(base64.b64decode(r['data']))

    print('\n===== A/B 结果 =====')
    for model in MODELS:
        for motion in MOTIONS:
            row = {'model': model, 'motion': motion}
            for side in ('old', 'new'):
                try:
                    lr = json.loads(load(model, side) or '{}')
                except Exception as e:
                    lr = {'fail': 'load ' + str(e)[:120]}
                if not lr.get('ok'):
                    row[side] = {'fail': lr.get('fail') or lr.get('skip') or lr}
                    continue
                try:
                    p = json.loads(play_and_probe(motion) or '{}')
                except Exception as e:
                    p = {'fail': 'probe ' + str(e)[:120]}
                tr = p.get('traces') or {}
                row[side] = {'fitK': lr['fitK'], 'natW': lr['natW'], 'groups': lr['groups'],
                             'uniqFrames': p.get('uniqFrames'), 'moved': p.get('movedParams'),
                             'cur': p.get('curGroup'), 'fail': p.get('fail') or p.get('skip'),
                             'AngleX': tr.get('ParamAngleX'), 'EyeLOpen': tr.get('ParamEyeLOpen')}
                shot(f'{model}_{side}_{motion}')
            print(json.dumps(row, ensure_ascii=False))

    ws.close(); proc.terminate(); srv.terminate()


if __name__ == '__main__':
    main()

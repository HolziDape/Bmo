"""
bmo_games.py — Mini-Spiele Blueprint (Pong Solo, Tetris, Snake, Breakout)
Wird in bmo_web_freund.py registriert.
"""
import math
import time
import secrets
import threading
from flask import Blueprint, request, jsonify, render_template_string
from flask import session as _flask_session, redirect, url_for

games_bp = Blueprint('games', __name__)


def _check_auth():
    """Returns True if user is authenticated (same check as login_required in bmo_web_freund)."""
    return bool(_flask_session.get('authenticated'))

# Aktive Spiel-Sessions: {token: {'game': str, 'start': float}}
_sessions: dict = {}
_sessions_lock  = threading.Lock()

# Basis-Punkte pro Spiel (Normal-Schwierigkeit)
BASE_POINTS = {
    'pong':     30,
    'tetris':   25,
    'snake':    20,
}

# Multiplikatoren pro Schwierigkeit
DIFF_MULTIPLIER = {
    'easy':   0.25,
    'normal': 0.5,
    'hard':   1.0,
    'insane': 3.0,
}

# Minimale Spielzeit (Anti-Cheat) pro (Spiel, Schwierigkeit)
MIN_GAME_SECONDS = {
    ('pong',     'easy'):   20,
    ('pong',     'normal'): 30,
    ('pong',     'hard'):   30,
    ('pong',     'insane'): 30,
    ('tetris',   'easy'):   30,
    ('tetris',   'normal'): 60,
    ('tetris',   'hard'):   60,
    ('tetris',   'insane'): 60,
    ('snake',    'easy'):   20,
    ('snake',    'normal'): 30,
    ('snake',    'hard'):   30,
    ('snake',    'insane'): 30,
}

# Spiel-spezifische Parameter pro Schwierigkeit (werden als Template-Variablen übergeben)
DIFF_PARAMS = {
    'pong': {
        'easy':   {'speed': 1.5, 'ai_factor': 0.03},
        'normal': {'speed': 2.5, 'ai_factor': 0.05},
        'hard':   {'speed': 4.0, 'ai_factor': 0.08},
        'insane': {'speed': 7,   'ai_factor': 0.19},
    },
    'tetris': {
        'easy':   {},
        'normal': {},
        'hard':   {},
        'insane': {},
    },
    'snake': {
        'easy':   {'tick': 200},
        'normal': {'tick': 150},
        'hard':   {'tick': 100},
        'insane': {'tick': 65},
    },
}

def _cleanup_sessions():
    """Entfernt Sessions die älter als 2 Stunden sind."""
    cutoff = time.time() - 7200
    with _sessions_lock:
        expired = [t for t, s in _sessions.items() if s['start'] < cutoff]
        for t in expired:
            del _sessions[t]


@games_bp.route('/games/<game>')
def game_page(game):
    if not _check_auth():
        return redirect('/login')
    if game not in BASE_POINTS:
        return 'Spiel nicht gefunden', 404
    diff = request.args.get('diff', 'normal')
    if diff not in DIFF_MULTIPLIER:
        diff = 'normal'
    earned = math.floor(BASE_POINTS[game] * DIFF_MULTIPLIER[diff])
    token = secrets.token_hex(16)
    with _sessions_lock:
        _sessions[token] = {'game': game, 'start': time.time(), 'diff': diff, 'earned': earned}
    _cleanup_sessions()
    params = DIFF_PARAMS[game][diff]
    return render_template_string(_GAME_PAGES[game], token=token, points=0, diff=diff, **params)


@games_bp.route('/api/games/complete', methods=['POST'])
def api_games_complete():
    """Spiel-Abschluss für Admin — keine Punkte."""
    if not _check_auth():
        return jsonify(error='Nicht eingeloggt'), 401
    data  = request.get_json(silent=True) or {}
    token = data.get('token', '')
    game  = data.get('game', '')
    with _sessions_lock:
        _sessions.pop(token, None)
    return jsonify(ok=True, earned=0, points=0, sig='')


# Game HTML pages — filled in Tasks 6-9
_PONG_HTML = r"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BMO Pong</title>
<style>
  body{margin:0;background:#0f172a;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100dvh;font-family:sans-serif;color:#e2e8f0;}
  canvas{border:2px solid #22c55e;border-radius:4px;touch-action:none;}
  #msg{font-size:18px;margin-top:16px;min-height:24px;color:#4ade80;}
  #info{font-size:14px;color:#64748b;margin-top:8px;}
  .diff-badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:700;margin-bottom:8px;}
  .easy{background:rgba(34,197,94,0.2);color:#4ade80;}.normal{background:rgba(59,130,246,0.2);color:#60a5fa;}
  .hard{background:rgba(249,115,22,0.2);color:#fb923c;}.insane{background:rgba(239,68,68,0.2);color:#f87171;}
</style>
</head>
<body>
<div class="diff-badge {{ diff }}">{{ diff|upper }}</div>
<h2 style="color:#4ade80;margin-bottom:4px;">🏓 BMO Pong Solo</h2>
<div id="info">Gewinne 10 Runden &rarr; +{{ points }} &#11088;</div>
<canvas id="c" width="420" height="260"></canvas>
<div id="msg">Bereit! Bewege die Maus oder tippe auf den Bildschirm.</div>
<script>
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
const W=canvas.width,H=canvas.height,PW=10,PH=60,BALL=8;
const SPEED={{ speed }}, AI_FACTOR={{ ai_factor }};
let py=(H-PH)/2,ay=(H-PH)/2,bx=W/2,by=H/2,vx=SPEED,vy=SPEED*(Math.random()>.5?1:-1);
let wins=0,losses=0,running=true,gameOver=false;

canvas.addEventListener('mousemove',e=>{
  const r=canvas.getBoundingClientRect();
  py=Math.min(H-PH,Math.max(0,e.clientY-r.top-PH/2));
});
canvas.addEventListener('touchmove',e=>{
  e.preventDefault();
  const r=canvas.getBoundingClientRect();
  py=Math.min(H-PH,Math.max(0,e.touches[0].clientY-r.top-PH/2));
},{passive:false});

function resetBall(dir){
  bx=W/2;by=H/2;
  vx=(SPEED+wins*0.1)*(dir||1);
  vy=(SPEED+wins*0.07)*(Math.random()>.5?1:-1);
}

function draw(){
  ctx.fillStyle='#0f172a';ctx.fillRect(0,0,W,H);
  ctx.setLineDash([8,8]);ctx.strokeStyle='#1e293b';ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(W/2,0);ctx.lineTo(W/2,H);ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle='#334155';ctx.font='bold 32px sans-serif';ctx.textAlign='center';
  ctx.fillText(wins,W/4,40);ctx.fillText(losses,3*W/4,40);
  ctx.fillStyle='#64748b';ctx.font='12px sans-serif';
  ctx.fillText('Wins',W/4,58);ctx.fillText('Verloren',3*W/4,58);
  ctx.fillStyle='#22c55e';ctx.beginPath();ctx.roundRect(4,py,PW,PH,4);ctx.fill();
  ctx.fillStyle='#ef4444';ctx.beginPath();ctx.roundRect(W-PW-4,ay,PW,PH,4);ctx.fill();
  ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(bx,by,BALL,0,Math.PI*2);ctx.fill();
}

function loop(){
  if(!running)return;
  const aim=by-(PH/2);
  ay+=(aim-ay)*AI_FACTOR;
  ay=Math.max(0,Math.min(H-PH,ay));
  bx+=vx;by+=vy;
  if(by-BALL<0){by=BALL;vy*=-1;}
  if(by+BALL>H){by=H-BALL;vy*=-1;}
  if(bx-BALL<PW+4&&by>py&&by<py+PH){bx=PW+4+BALL;vx=Math.abs(vx)*(1+0.05*wins);vy+=(by-(py+PH/2))*0.1;}
  if(bx+BALL>W-PW-4&&by>ay&&by<ay+PH){bx=W-PW-4-BALL;vx=-Math.abs(vx)*(1+0.05*wins);}
  if(bx<0){losses++;document.getElementById('msg').textContent='Verloren! '+wins+'/10 Wins';resetBall(1);}
  if(bx>W){wins++;document.getElementById('msg').textContent=wins<10?'Gewonnen! '+wins+'/10 Wins':' ';resetBall(-1);}
  draw();
  if(wins>=10&&!gameOver){gameOver=true;running=false;finish();}
  else requestAnimationFrame(loop);
}

async function finish(){
  document.getElementById('msg').textContent='10 Wins! Punkte werden gutgeschrieben...';
  const stored=JSON.parse(localStorage.getItem('bmo_points')||'{}');
  const r=await fetch('/api/games/complete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token:'{{ token }}',game:'pong',points:stored.points||0,sig:stored.sig||''})});
  const d=await r.json();
  if(d.error){document.getElementById('msg').textContent='Fehler: '+d.error;return;}
  localStorage.setItem('bmo_points',JSON.stringify({points:d.points,sig:d.sig}));
  document.getElementById('msg').textContent='+'+d.earned+' \u2B50 \u2192 jetzt '+d.points+' Punkte! Fenster schlie\xDFen.';
}

resetBall();loop();
</script>
<button onclick="location.reload()" style="margin-top:16px;background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:8px 20px;border-radius:10px;font-size:14px;cursor:pointer;">&#8635; Neu starten</button>
</body>
</html>"""

_TETRIS_HTML = r"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BMO Tetris</title>
<style>
  body{margin:0;background:#0f172a;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100dvh;font-family:sans-serif;color:#e2e8f0;}
  canvas{border:2px solid #a855f7;border-radius:4px;}
  #msg{font-size:16px;margin-top:12px;min-height:20px;color:#c084fc;}
  .ctrl{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;justify-content:center;}
  .ctrl button{background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:10px 18px;border-radius:10px;font-size:18px;cursor:pointer;}
  .diff-badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:700;margin-bottom:4px;}
  .easy{background:rgba(34,197,94,0.2);color:#4ade80;}.normal{background:rgba(59,130,246,0.2);color:#60a5fa;}
  .hard{background:rgba(249,115,22,0.2);color:#fb923c;}.insane{background:rgba(239,68,68,0.2);color:#f87171;}
</style>
</head>
<body>
<div class="diff-badge {{ diff }}">{{ diff|upper }}</div>
<h2 style="color:#c084fc;margin-bottom:4px;">&#129689; BMO Tetris</h2>
<div style="font-size:13px;color:#64748b;margin-bottom:8px;">Level 5 erreichen &rarr; +{{ points }} &#11088;</div>
<canvas id="c" width="200" height="400"></canvas>
<div id="msg">&#8592; &#8594; bewegen | &#8593; drehen | &#8595; fallen | Leertaste: sofort</div>
<div class="ctrl">
  <button ontouchstart="move(-1)">&#9664;</button>
  <button ontouchstart="rotate()">&#128260;</button>
  <button ontouchstart="move(1)">&#9654;</button>
  <button ontouchstart="drop()">&#9660;</button>
  <button ontouchstart="hardDrop()" style="border-color:#a855f7;color:#c084fc;">&#9660;&#9660;</button>
</div>
<script>
const COLS=10,ROWS=20,SZ=20;
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
const PIECES=[
  {s:[[1,1,1,1]],c:'#22d3ee'},
  {s:[[1,0],[1,0],[1,1]],c:'#f97316'},
  {s:[[0,1],[0,1],[1,1]],c:'#3b82f6'},
  {s:[[1,1],[1,1]],c:'#facc15'},
  {s:[[0,1,1],[1,1,0]],c:'#22c55e'},
  {s:[[1,1,0],[0,1,1]],c:'#ef4444'},
  {s:[[1,1,1],[0,1,0]],c:'#a855f7'},
];
let board=Array.from({length:ROWS},()=>Array(COLS).fill(0));
let cur,cx,cy,score=0,level=1,lines=0,gameOver=false,done=false;

function newPiece(){
  const p=PIECES[Math.floor(Math.random()*PIECES.length)];
  cur={s:p.s.map(r=>[...r]),c:p.c};
  cx=Math.floor((COLS-cur.s[0].length)/2);cy=0;
  if(!fits(cur.s,cx,cy)){gameOver=true;document.getElementById('msg').textContent='Game Over!';}
}

function fits(s,x,y){
  for(let r=0;r<s.length;r++)for(let c=0;c<s[r].length;c++)
    if(s[r][c]&&(y+r>=ROWS||x+c<0||x+c>=COLS||board[y+r][x+c]))return false;
  return true;
}

function ghostY(){
  let gy=cy;
  while(fits(cur.s,cx,gy+1))gy++;
  return gy;
}

function place(){
  cur.s.forEach((r,ri)=>r.forEach((v,ci)=>{if(v)board[cy+ri][cx+ci]=cur.c;}));
  let cleared=0;
  board=board.filter(r=>{if(r.every(c=>c)){cleared++;return false;}return true;});
  while(board.length<ROWS)board.unshift(Array(COLS).fill(0));
  lines+=cleared;score+=cleared*100;
  level=Math.floor(lines/10)+1;
  document.getElementById('msg').textContent='Level '+level+' | Zeilen '+lines+' | Score '+score;
  if(level>=5&&!done){done=true;finish();return;}
  newPiece();
}

function move(d){if(!gameOver&&!done&&fits(cur.s,cx+d,cy))cx+=d;}
function drop(){if(!gameOver&&!done&&fits(cur.s,cx,cy+1))cy++;else if(!gameOver&&!done)place();}
function hardDrop(){
  if(gameOver||done)return;
  cy=ghostY();
  place();
}
function rotate(){
  if(gameOver||done)return;
  const r=cur.s[0].map((_,i)=>cur.s.map(row=>row[i]).reverse());
  if(fits(r,cx,cy))cur.s=r;
}

document.addEventListener('keydown',e=>{
  if(e.key==='ArrowLeft')move(-1);
  if(e.key==='ArrowRight')move(1);
  if(e.key==='ArrowDown')drop();
  if(e.key==='ArrowUp')rotate();
  if(e.key===' '){e.preventDefault();hardDrop();}
});

function draw(){
  ctx.fillStyle='#0f172a';ctx.fillRect(0,0,200,400);
  for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++){
    const v=board[r][c];
    ctx.fillStyle=v||'#0f172a';
    ctx.fillRect(c*SZ,r*SZ,SZ-1,SZ-1);
  }
  // Ghost piece
  if(cur&&!done&&!gameOver){
    const gy=ghostY();
    if(gy!==cy){
      ctx.globalAlpha=0.25;
      cur.s.forEach((r,ri)=>r.forEach((v,ci)=>{
        if(v){ctx.fillStyle=cur.c;ctx.fillRect((cx+ci)*SZ,(gy+ri)*SZ,SZ-1,SZ-1);}
      }));
      ctx.globalAlpha=1;
    }
    // Actual piece
    cur.s.forEach((r,ri)=>r.forEach((v,ci)=>{
      if(v){ctx.fillStyle=cur.c;ctx.fillRect((cx+ci)*SZ,(cy+ri)*SZ,SZ-1,SZ-1);}
    }));
  }
}

let last=0;
function loop(ts){
  if(gameOver||done)return;
  if(ts-last>Math.max(100,600-level*50)){last=ts;drop();}
  draw();requestAnimationFrame(loop);
}

async function finish(){
  document.getElementById('msg').textContent='Level 5! Punkte werden gutgeschrieben...';
  const stored=JSON.parse(localStorage.getItem('bmo_points')||'{}');
  const r=await fetch('/api/games/complete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token:'{{ token }}',game:'tetris',points:stored.points||0,sig:stored.sig||''})});
  const d=await r.json();
  if(d.error){document.getElementById('msg').textContent='Fehler: '+d.error;return;}
  localStorage.setItem('bmo_points',JSON.stringify({points:d.points,sig:d.sig}));
  document.getElementById('msg').textContent='+'+d.earned+' \u2B50 \u2192 jetzt '+d.points+' Punkte!';
}

newPiece();
document.getElementById('msg').textContent='Level '+level+' | Zeilen '+lines+' | Score '+score;
requestAnimationFrame(loop);
</script>
<button onclick="location.reload()" style="margin-top:12px;background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:8px 20px;border-radius:10px;font-size:14px;cursor:pointer;">&#8635; Neu starten</button>
</body>
</html>"""

_SNAKE_HTML = r"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BMO Snake</title>
<style>
  body{margin:0;background:#0f172a;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100dvh;font-family:sans-serif;color:#e2e8f0;}
  canvas{border:2px solid #22c55e;border-radius:4px;}
  #msg{font-size:16px;margin-top:12px;min-height:20px;color:#4ade80;}
  .ctrl{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px;width:150px;}
  .ctrl button{background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:12px;border-radius:10px;font-size:18px;cursor:pointer;}
  .diff-badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:700;margin-bottom:4px;}
  .easy{background:rgba(34,197,94,0.2);color:#4ade80;}.normal{background:rgba(59,130,246,0.2);color:#60a5fa;}
  .hard{background:rgba(249,115,22,0.2);color:#fb923c;}.insane{background:rgba(239,68,68,0.2);color:#f87171;}
</style>
</head>
<body>
<div class="diff-badge {{ diff }}">{{ diff|upper }}</div>
<h2 style="color:#4ade80;margin-bottom:4px;">&#128013; BMO Snake</h2>
<div style="font-size:13px;color:#64748b;margin-bottom:8px;">20 &#196;pfel essen &rarr; +{{ points }} &#11088;</div>
<canvas id="c" width="300" height="300"></canvas>
<div id="msg">WASD oder Pfeiltasten</div>
<div class="ctrl">
  <div></div><button ontouchstart="setDir(0,-1)">&#9650;</button><div></div>
  <button ontouchstart="setDir(-1,0)">&#9664;</button>
  <button ontouchstart="setDir(0,1)">&#9660;</button>
  <button ontouchstart="setDir(1,0)">&#9654;</button>
</div>
<script>
const SZ=20,COLS=15,ROWS=15,TICK={{ tick }};
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
let snake=[{x:7,y:7}],dir={x:1,y:0},nextDir={x:1,y:0};
let apple={x:3,y:3},eaten=0,dead=false,done=false;

function randApple(){
  let a;
  do{a={x:Math.floor(Math.random()*COLS),y:Math.floor(Math.random()*ROWS)};}
  while(snake.some(s=>s.x===a.x&&s.y===a.y));
  apple=a;
}

function setDir(x,y){if(snake.length>1&&x===-dir.x&&y===-dir.y)return;nextDir={x,y};}
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowLeft'||e.key==='a')setDir(-1,0);
  if(e.key==='ArrowRight'||e.key==='d')setDir(1,0);
  if(e.key==='ArrowUp'||e.key==='w')setDir(0,-1);
  if(e.key==='ArrowDown'||e.key==='s')setDir(0,1);
});

function step(){
  if(dead||done)return;
  dir=nextDir;
  const head={x:snake[0].x+dir.x,y:snake[0].y+dir.y};
  if(head.x<0||head.x>=COLS||head.y<0||head.y>=ROWS||snake.some(s=>s.x===head.x&&s.y===head.y)){
    dead=true;document.getElementById('msg').textContent='Kollision! Seite neu laden zum Weiterspielen.';return;
  }
  snake.unshift(head);
  if(head.x===apple.x&&head.y===apple.y){
    eaten++;document.getElementById('msg').textContent=eaten+'/20 \u00C4pfel';
    randApple();
    if(eaten>=20){done=true;finish();}
  } else {
    snake.pop();
  }
}

function draw(){
  ctx.fillStyle='#0f172a';ctx.fillRect(0,0,300,300);
  ctx.fillStyle='#ef4444';ctx.fillRect(apple.x*SZ+2,apple.y*SZ+2,SZ-4,SZ-4);
  snake.forEach((s,i)=>{
    ctx.fillStyle=i===0?'#4ade80':'#22c55e';
    ctx.fillRect(s.x*SZ+1,s.y*SZ+1,SZ-2,SZ-2);
  });
}

async function finish(){
  document.getElementById('msg').textContent='20 \u00C4pfel! Punkte werden gutgeschrieben...';
  const stored=JSON.parse(localStorage.getItem('bmo_points')||'{}');
  const r=await fetch('/api/games/complete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token:'{{ token }}',game:'snake',points:stored.points||0,sig:stored.sig||''})});
  const d=await r.json();
  if(d.error){document.getElementById('msg').textContent='Fehler: '+d.error;return;}
  localStorage.setItem('bmo_points',JSON.stringify({points:d.points,sig:d.sig}));
  document.getElementById('msg').textContent='+'+d.earned+' \u2B50 \u2192 jetzt '+d.points+' Punkte!';
}

randApple();
setInterval(()=>{step();draw();},TICK);
</script>
<button onclick="location.reload()" style="margin-top:12px;background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:8px 20px;border-radius:10px;font-size:14px;cursor:pointer;">&#8635; Neu starten</button>
</body>
</html>"""

_GAME_PAGES: dict = {
    'pong':   _PONG_HTML,
    'tetris': _TETRIS_HTML,
    'snake':  _SNAKE_HTML,
}

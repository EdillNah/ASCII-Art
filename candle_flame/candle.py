# Candle Flame & Flying Fire - ASCII Art Visualizer
# Ajetz_ · @aidildn_ · 2026.
#
#   pip install -r requirements.txt
#   python candle.py
#
# Space pause, R restart, S screenshot, Esc quit

import math
import sys
import time
from pathlib import Path

import numpy as np
import pygame

TAU = np.pi * 2
LOOP = 24.0         # durasi satu putaran penuh (s)
IGNITE = 6.4        # saat roh api terbang menyentuh sumbu lilin

POOLS = ["1il!;:", "rtfjcvxz=+", "aeoun0{}[]<>", "08B$#&%Q"]   # dark -> bright
CHARS = " .,:~+*^01|/\\-_#()x" + "".join(POOLS)
AT = {c: i for i, c in enumerate(CHARS)}
FILL = np.array([[AT[p[k % len(p)]] for k in range(12)] for p in POOLS])


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


#             blue base       white hot        gold            orange          deep red        wax ivory       brass dish      smoke           dust
TAG_COLOR = [[90, 165, 255], [255, 252, 230], [255, 185, 45], [255, 115, 20], [210, 42, 14], [235, 222, 198], [175, 138, 68], [112, 105, 126], [150, 120, 100]]
BLUE, HOT, GOLD, ORANGE, RED, WAX, BRASS, SMOKE, DUST = range(9)

_grid = {}


def grid(cols, rows, aspect):
    key = (cols, rows)
    if key not in _grid:
        rng = np.random.default_rng(42)
        x = ((np.arange(cols) + 0.5) / cols - 0.5) * aspect
        y = (np.arange(rows) + 0.5) / rows - 0.5
        X, Y = np.meshgrid(x, y)
        _grid[key] = X, Y, rng.random((rows, cols)), rng.integers(0, 12, (rows, cols))
    return _grid[key]


def tangent_letter(dx, dy):
    s = np.degrees(np.arctan2(-dy, dx)) % 180
    out = np.full(s.shape, AT["\\"])
    out[(s < 22.5) | (s >= 157.5)] = AT["-"]
    out[(s >= 22.5) & (s < 67.5)] = AT["/"]
    out[(s >= 67.5) & (s < 112.5)] = AT["|"]
    return out


# ==========================================
# TRAJEKTORI ROH API TERBANG (FLYING FLAME)
# ==========================================
def flying_flame_pos(t, wick_x=0.0, wick_y=0.038):
    if t >= IGNITE:
        return wick_x, wick_y, 0.0, 0.0

    u = max(0.0, min(1.0, t / IGNITE))

    # Titik-titik waypoint lintasan kurva sinematik di ruang normalisasi (X, Y)
    # Start di kiri atas -> meluncur ke kanan bawah -> meliuk ke tengah -> menukik ke sumbu
    p0 = np.array([-0.42, -0.34])
    p1 = np.array([0.38, -0.16])
    p2 = np.array([-0.30, 0.06])
    p3 = np.array([wick_x, wick_y])

    pos = (1.0 - u) ** 3 * p0 + 3 * (1.0 - u) ** 2 * u * p1 + 3 * (1.0 - u) * u ** 2 * p2 + u ** 3 * p3

    # Ayunan melayang roh api organik
    flutter = 1.0 - u ** 1.5
    fx = pos[0] + (0.016 * np.sin(7.5 * t) + 0.008 * np.sin(14.8 * t)) * flutter
    fy = pos[1] + (0.012 * np.cos(6.2 * t) + 0.006 * np.cos(12.3 * t)) * flutter

    # Estimasi arah dan vektor kecepatan untuk orientasi ekor api
    dt = 0.02
    u2 = min(1.0, u + dt / IGNITE)
    pos2 = (1.0 - u2) ** 3 * p0 + 3 * (1.0 - u2) ** 2 * u2 * p1 + 3 * (1.0 - u2) * u2 ** 2 * p2 + u2 ** 3 * p3
    vx = (pos2[0] - pos[0]) / dt
    vy = (pos2[1] - pos[1]) / dt

    return float(fx), float(fy), float(vx), float(vy)


# ==========================================
# RENDER FRAME SIMULASI ASCII
# ==========================================
def frame(t, cols, rows, aspect):
    X, Y, rnd, hsh = grid(cols, rows, aspect)

    # Titik geometris lilin
    WICK_X = 0.0
    WICK_Y = 0.038
    WAX_TOP = 0.075
    WAX_BASE = 0.360
    WAX_R = 0.082

    # Progres penyalaan lilin (0.0 = padam, 1.0 = menyala penuh)
    k_ignite = smooth((t - IGNITE) / 0.8)

    # 1. POSISI API TERBANG & VISIBILITAS GELAP/TERANG
    fx, fy, fvx, fvy = flying_flame_pos(t, WICK_X, WICK_Y)

    dist_fly = np.hypot(X - fx, Y - fy)
    r_wick = np.hypot(X - WICK_X, Y - WICK_Y)

    # Radius jangkauan lentera api terbang sebelum lilin menyala
    # DI LUAR JANGKAUAN INI, RUANGAN GELAP TOTAL (PITCH BLACK)
    light_radius = 0.16
    light_fly = np.exp(-((dist_fly / 0.10) ** 2)) * (1.0 - k_ignite)
    fly_visibility = smooth((light_radius - dist_fly) / 0.06) * (1.0 - k_ignite)

    # 2. GELOMBANG LINGKARAN CAHAYA SAAT IGNISI (EXPANDING CIRCULAR SHOCKWAVE)
    wave_ring = np.zeros_like(X)
    awakening = np.zeros_like(X)
    flash = np.zeros_like(X)

    if t >= IGNITE:
        dt_ignite = t - IGNITE
        # Gelombang lingkaran merambat membesar dari sumbu lilin ke seluruh layar
        r_wave = dt_ignite * 0.52

        # Cincin gelombang lingkaran berenergi terang
        wave_ring = np.exp(-(((r_wick - r_wave) / 0.024) ** 2)) * np.exp(-dt_ignite / 1.8) * 1.6
        # Seluruh pemandangan di dalam lingkaran gelombang tersulut dan MENYALA
        awakening = smooth((r_wave - r_wick) / 0.04)
        # Kilatan putih menyilaukan di titik kontak sumbu
        flash = np.exp(-((dt_ignite / 0.22) ** 2)) * np.exp(-((r_wick / 0.06) ** 2)) * 2.2

    # Visibilitas total pemandangan:
    # Hanya terlihat di sekitar jangkauan api terbang ATAU di dalam lingkaran gelombang yang menyapu
    visibility = np.maximum(fly_visibility, awakening)

    # Cahaya lilin yang berkedip lembut di ruangan
    flicker = 1.0 + 0.08 * np.sin(18.0 * t) + 0.04 * np.sin(37.0 * t) + 0.02 * np.sin(65.0 * t)
    light_candle = np.exp(-((r_wick) / 0.26) ** 1.5) * k_ignite * flicker * awakening

    light_total = light_fly + light_candle

    # 3. ROH API TERBANG (FLYING FLAME WISP)
    fly_heat = np.zeros_like(X)
    fly_speed = math.hypot(fvx, fvy)
    if t < IGNITE + 0.3:
        dx_f = X - fx
        dy_f = Y - fy
        if fly_speed > 0.01:
            ca = fvx / fly_speed
            sa = fvy / fly_speed
            along = dx_f * ca + dy_f * sa
            across = -dx_f * sa + dy_f * ca
        else:
            along = dy_f
            across = dx_f

        # Bentuk tetesan api dengan ekor meruncing ke belakang arah gerak
        tail = np.where(along < 0, 1.0 + np.abs(along) * 35.0, 1.0)
        r_flame = np.hypot(across * tail * 1.4, along)
        fade_fly = smooth((IGNITE + 0.3 - t) / 0.3)
        fly_heat = np.exp(-((r_flame) / 0.024) ** 1.8) * fade_fly

    # 4. NYALA API LILIN (CANDLE FLAME FIELD)
    candle_heat = np.zeros_like(X)
    blue_core_mask = np.zeros(X.shape, dtype=bool)
    flame_edge_mask = np.zeros(X.shape, dtype=bool)

    if k_ignite > 0.01:
        flame_h = 0.17 * k_ignite
        y_up = WICK_Y - Y
        in_flame_y = (y_up >= 0.0) & (y_up <= flame_h)

        y_norm = np.clip(y_up / flame_h, 0.0, 1.0)
        # Liukan api organik
        flicker_disp = (0.009 * np.sin(32.0 * y_norm - 9.0 * t) + 0.004 * np.sin(70.0 * y_norm + 16.0 * t)) * (y_norm ** 1.2)
        x_flame = X - (WICK_X + flicker_disp)

        flame_w = np.maximum(0.003, 0.040 * k_ignite * np.sin(np.pi * (y_norm ** 0.55)) * (1.0 - 0.25 * y_norm))
        c_ratio = np.abs(x_flame) / flame_w
        heat_c = np.exp(-(c_ratio ** 2 * 2.6)) * (1.0 - y_norm ** 1.3) * flicker
        candle_heat = np.where(in_flame_y, heat_c, 0.0)

        # Dasar api biru hidrokarbon di pangkal sumbu
        blue_core_mask = in_flame_y & (y_norm < 0.20) & (c_ratio < 0.95)
        # Deteksi garis kontur api
        flame_edge_mask = in_flame_y & (c_ratio >= 0.85) & (c_ratio <= 1.2) & (heat_c > 0.12)

    # 5. ASAP TIPIS MELIUK KE ATAS (SMOKE PLUME)
    smoke_heat = np.zeros_like(X)
    if k_ignite > 0.3:
        flame_h = 0.17 * k_ignite
        y_smoke = (WICK_Y - flame_h) - Y
        in_smoke_y = (y_smoke > 0.0) & (Y > -0.48)
        s_norm = np.clip(y_smoke / 0.45, 0.0, 1.0)

        smoke_wave = 0.032 * np.sin(16.0 * s_norm - 2.8 * t) + 0.016 * np.cos(34.0 * s_norm + 1.5 * t) + 0.02 * s_norm
        smoke_w = 0.018 + 0.065 * s_norm
        d_smoke = np.abs(X - (WICK_X + smoke_wave)) / smoke_w
        heat_sm = np.exp(-(d_smoke ** 2 * 2.4)) * np.exp(-s_norm * 1.5) * 0.38 * k_ignite * awakening
        smoke_heat = np.where(in_smoke_y, heat_sm, 0.0)

    # 6. BADAN LILIN & TATAKAN KUNINGAN (HANYA TERLIHAT JIKA TERKENA CAHAYA)
    in_pillar_y = (Y >= WAX_TOP) & (Y < WAX_BASE)
    drip = 1.0 + 0.06 * np.sin(42.0 * Y) + 0.04 * np.cos(105.0 * Y)
    dx_wax = X / (WAX_R * drip)
    in_wax_body = in_pillar_y & (np.abs(dx_wax) <= 1.0)

    # Shading 3D Silinder (dikalikan visibilitas: gelap total jika belum disinari)
    norm_z = np.sqrt(np.maximum(0.0, 1.0 - np.clip(dx_wax, -1.0, 1.0) ** 2))
    sss = np.clip(1.0 - (Y - WAX_TOP) / 0.08, 0.0, 1.0) * k_ignite * 0.45
    wax_heat = np.where(in_wax_body, (0.12 + 0.42 * norm_z + 0.55 * light_total + sss) * visibility, 0.0)

    # Cekungan atas lilin (Melted rim)
    rim_dy = (Y - WAX_TOP) / 0.022
    rim_dist = np.hypot(dx_wax, rim_dy)
    in_rim = (rim_dist <= 1.05) & (Y <= WAX_TOP + 0.015)
    rim_heat = np.where(in_rim, (0.28 + 0.70 * light_total) * visibility, 0.0)

    # Tatakan piring kuningan di dasar
    in_holder_y = (Y >= WAX_BASE) & (Y <= WAX_BASE + 0.045)
    holder_r = WAX_R * (2.4 - (Y - WAX_BASE) / 0.045 * 0.8)
    in_holder = in_holder_y & (np.abs(X) <= holder_r)
    holder_heat = np.where(in_holder, (0.18 + 0.50 * light_total) * visibility, 0.0)

    # Sumbu lilin
    in_wick = (Y >= WICK_Y) & (Y <= WAX_TOP + 0.005) & (np.abs(X - WICK_X) <= 0.0035)
    wick_heat = np.where(in_wick, (0.25 + 0.75 * k_ignite) * np.maximum(visibility, k_ignite), 0.0)

    # 7. GABUNGAN ENERGI (HEAT COMPOSITING)
    # Blend screen untuk api, gelombang lingkaran, dan kilatan
    fire_blend = 1.0 - (1.0 - np.clip(fly_heat, 0, 1)) * (1.0 - np.clip(candle_heat, 0, 1)) * (1.0 - np.clip(wave_ring, 0, 1))
    fire_blend = np.maximum(fire_blend, np.maximum(fly_heat, candle_heat))
    total_fire = fire_blend + flash

    # Total heat di seluruh grid layar
    heat = np.maximum.reduce([total_fire, wax_heat, rim_heat, holder_heat, wick_heat, smoke_heat])

    # 8. PEMETAAN KARAKTER ASCII & LEVEL DENSITY
    on = heat > 0.06
    level = np.clip((heat * 3.6).astype(int), 0, 3)
    char = FILL[level, (hsh + (X * 12 + Y * 25 + t * 4).astype(int)) % 12]

    # Karakter spesifik untuk elemen lilin (hanya muncul saat ada energi/panas)
    char = np.where(in_wax_body & ~in_rim & on, np.where(wax_heat > 0.65, AT["#"], np.where(wax_heat > 0.40, AT["0"], AT[":"])), char)
    char = np.where(in_rim & on, AT["_"], char)
    char = np.where(in_holder & on, AT["="], char)
    char = np.where(in_wick & on, AT["|"], char)
    char = np.where(smoke_heat > 0.08, np.where(smoke_heat > 0.22, AT["~"], AT[";"]), char)

    # Tangent letter untuk kontur tepi api dan CINCIN GELOMBANG LINGKARAN
    is_wave_edge = (wave_ring > 0.28) & (wave_ring > total_fire * 0.70)
    char = np.where(is_wave_edge, tangent_letter(-X, Y - WICK_Y), char)
    char = np.where(flame_edge_mask, tangent_letter(-X, Y - WICK_Y), char)

    # Matikan karakter di area luar yang gelap pekat
    char = np.where(on, char, AT[" "])

    # 9. PEMETAAN KATEGORI WARNA (TAG PALETTE)
    tag = np.select(
        [heat < 0.12, heat < 0.28, heat < 0.55, heat < 0.85],
        [RED, ORANGE, GOLD, HOT],
        HOT
    )
    tag = np.where(blue_core_mask, BLUE, tag)
    tag = np.where(in_wax_body | in_rim, WAX, tag)
    tag = np.where(in_holder, BRASS, tag)
    tag = np.where(in_wick, np.where(k_ignite > 0.1, RED, DUST), tag)
    tag = np.where(smoke_heat > 0.08, SMOKE, tag)
    # Gelombang lingkaran bersinar emas-putih terang
    tag = np.where(is_wave_edge, np.where(wave_ring > 0.6, HOT, GOLD), tag)

    # 10. LUMINOSITAS
    lum = np.where(on, np.clip(0.42 + 0.85 * heat, 0.0, 1.4) * (0.35 + 0.65 * smooth((heat - 0.06) / 0.15)), 0.0)

    # 11. DEBU & PARTIKEL CAHAYA DI KEGELAPAN (HANYA MUNCUL DI DAERAH YANG TERANG)
    is_spark_trail = (t < IGNITE) & (dist_fly < 0.12) & (rnd < 0.040) & ~on
    # Bintang/debu di latar belakang HANYA muncul jika sudah tersapu oleh gelombang lingkaran!
    star = (~on & ~in_wax_body & (rnd < 0.0024) & (visibility > 0.85)) | is_spark_trail
    char = np.where(star, np.where(rnd < 0.0007, AT["+"], np.where(rnd < 0.0016, AT["*"], AT["."])), char)
    tag = np.where(star, np.where(is_spark_trail, GOLD, DUST), tag)
    lum = np.where(star, 0.75 + 0.25 * np.sin(1.2 * t + rnd * 8000), lum)

    count = int((char != AT[" "]).sum())
    state_str = "APPROACHING" if t < IGNITE else ("WAVE IGNITION" if t < IGNITE + 1.6 else "BURNING")
    info = {
        "t": float(t),
        "state": state_str,
        "heat": float(heat.max()),
        "fx": float(fx),
        "fy": float(fy),
    }

    return char.astype(int), lum.astype(np.float32), tag.astype(int), info, count


# ==========================================
# WINDOW & DISPLAY ENGINE
# ==========================================
TITLE = "ASCII - Ajetz_"
SIGN = "@aidildn_ · 2026"
SUBTITLE = "Candle Flame & Flying Fire · Procedural ASCII"

CW, CH, FONT_PX = 7, 11, 12
W, H = 1080, 960
COLS, ROWS = W // CW, H // CH
ASPECT = (COLS * CW) / (ROWS * CH)
TRAIL = 0.38
COLORS = np.array(TAG_COLOR, np.float32) / 255
DIM, GOLD_UI, PINK = (115, 108, 125), (255, 195, 120), (255, 122, 182)
MONO = "consolas,menlo,dejavusansmono,couriernew,monospace"


def hud(info):
    return f"state {info['state']:<14}  heat {info['heat']:.2f}  pos ({info['fx']:+.2f}, {info['fy']:+.2f})"


def glyphs():
    font = pygame.font.SysFont(MONO, FONT_PX)
    atlas = []
    for ch in CHARS:
        s = pygame.Surface((CW, CH))
        g = font.render(ch, True, (255, 255, 255))
        s.blit(g, ((CW - g.get_width()) // 2, (CH - g.get_height()) // 2))
        atlas.append(pygame.surfarray.array3d(s)[:, :, 0].T.astype(np.float32) / 255)
    return np.stack(atlas)


class Canvas:
    def __init__(self, atlas):
        self.atlas = (atlas * 255).astype(np.uint8)
        self.shape = pygame.Surface((COLS * CW, ROWS * CH))
        self.trail = pygame.Surface((W, H))
        self.fade = (int(TRAIL * 255),) * 3

    def reset(self):
        self.trail.fill((0, 0, 0))

    def draw(self, t):
        char, lum, tag, info, count = frame(t, COLS, ROWS, ASPECT)
        mask = self.atlas[char.T].transpose(0, 3, 1, 2).reshape(COLS * CW, ROWS * CH)
        pygame.surfarray.blit_array(self.shape, np.repeat(mask[..., None], 3, 2))
        col = np.clip(COLORS[np.clip(tag, 0, len(COLORS) - 1)] * lum[..., None] * 255, 0, 255).astype(np.uint8)
        tint = pygame.transform.scale(pygame.surfarray.make_surface(col.transpose(1, 0, 2)), self.shape.get_size())
        self.shape.blit(tint, (0, 0), special_flags=pygame.BLEND_MULT)
        self.trail.fill(self.fade, special_flags=pygame.BLEND_MULT)     # Jejak pergerakan pudar halus
        self.trail.blit(self.shape, (0, 0), special_flags=pygame.BLEND_MAX)
        return self.trail, info, count


def blur(surf, k, radius):
    small = pygame.transform.smoothscale(surf, (W // k, H // k))
    if hasattr(pygame.transform, "gaussian_blur"):
        small = pygame.transform.gaussian_blur(small, max(1, radius // k))
    return pygame.transform.smoothscale(small, (W, H))


def glow_layer(surf, amount):
    layer = surf.copy()
    layer.fill((int(255 * amount),) * 3, special_flags=pygame.BLEND_MULT)
    return layer


def window_size():
    info = pygame.display.Info()
    k = 1.0
    if info.current_w > 0 and info.current_h > 0:
        k = min(1.0, 0.88 * info.current_h / H, 0.95 * info.current_w / W)
    return int(W * k), int(H * k)


def main():
    pygame.init()
    size = window_size()
    window = pygame.display.set_mode(size)
    pygame.display.set_caption(TITLE)   # Watermark judul luar: Ajetz_
    screen = pygame.Surface((W, H))
    small = pygame.font.SysFont(MONO, 17)
    canvas, clock = Canvas(glyphs()), pygame.time.Clock()
    t, paused = 0.0, False
    art, info, count = canvas.draw(t)

    toast_msg = ""
    toast_expire = 0.0
    take_screenshot = False

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, 27):
                    pygame.quit()
                    return
                elif e.key in (pygame.K_SPACE, ord(' ')):
                    paused = not paused
                    if paused:
                        toast_msg = "[PAUSED] Simulasi Dijeda (Tekan SPASI untuk lanjut)"
                        toast_expire = time.time() + 999999.0
                    else:
                        toast_msg = "[RESUMED] Melanjutkan simulasi..."
                        toast_expire = time.time() + 1.2
                elif e.key in (pygame.K_r, ord('r'), ord('R')):
                    t = 0.0
                    canvas.reset()
                    toast_msg = "[RESTART] Mengulang simulasi dari awal (t = 0.00s)"
                    toast_expire = time.time() + 1.8
                elif e.key in (pygame.K_s, ord('s'), ord('S')):
                    take_screenshot = True

        dt = clock.tick(30) / 1000
        if not paused:
            t += min(dt, 1 / 15)
            if t > LOOP:
                t = 0.0
                canvas.reset()
            art, info, count = canvas.draw(t)

        screen.fill((0, 0, 0))
        screen.blit(art, (0, 0))

        # Lapisan Glow & Bloom Berlapis
        screen.blit(glow_layer(blur(art, 4, 5), 0.75), (0, 0), special_flags=pygame.BLEND_ADD)
        screen.blit(glow_layer(blur(art, 8, 22), 0.45), (0, 0), special_flags=pygame.BLEND_ADD)

        # UI & Watermark di Layar (Sudut Kiri Bawah)
        y = H - 70
        screen.blit(small.render(SIGN, True, GOLD_UI), (64, y - 26))
        screen.blit(small.render(hud(info), True, DIM), (64, y))
        screen.blit(small.render(f"letters {count:05,d}", True, DIM), (64, y + 26))

        # Waktu & Status di Sudut Kanan Atas
        tt = small.render(f"{'●' if int(t * 2) % 2 == 0 else ' '} t {t:05.2f}s", True, PINK)
        screen.blit(tt, (W - 64 - tt.get_width(), 30))

        # Watermark judul aplikasi di Sudut Kiri Atas
        title_badge = small.render(TITLE, True, (255, 175, 90))
        screen.blit(title_badge, (64, 30))

        # Petunjuk Tombol Kontrol (Sudut Kanan Bawah)
        help_text = "[SPASI] Pause   [R] Restart   [S] Screenshot   [ESC] Exit"
        help_surf = small.render(help_text, True, (130, 130, 150))
        screen.blit(help_surf, (W - 64 - help_surf.get_width(), H - 44))

        # Indikator Status / Toast Notifikasi
        now = time.time()
        if toast_msg and now < toast_expire:
            toast_surf = small.render(toast_msg, True, (255, 220, 120))
            tx = (W - toast_surf.get_width()) // 2
            screen.blit(toast_surf, (tx, 30))

        # Tangkap Screenshot jika tombol S ditekan
        if take_screenshot:
            take_screenshot = False
            base_dir = Path(__file__).resolve().parent
            img_dir = base_dir / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            shot_name = f"ajetz_candle_{int(time.time())}.png"
            # Simpan di folder images/ dan folder root candle_flame
            pygame.image.save(screen, str(img_dir / shot_name))
            pygame.image.save(screen, str(base_dir / shot_name))
            toast_msg = f"[SCREENSHOT TERSIMPAN] {shot_name}"
            toast_expire = time.time() + 2.5
            print(f"[SCREENSHOT] Berhasil disimpan ke images/{shot_name} dan {shot_name}")

        window.blit(screen if size == (W, H) else pygame.transform.smoothscale(screen, size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    sys.exit(main())

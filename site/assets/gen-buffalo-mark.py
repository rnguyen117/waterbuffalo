import random, math, sys

random.seed(11)

# --- Geometric water buffalo head, side profile, facing left. ---
# x=0 is the muzzle tip (most visible / leftmost); the shape runs right
# into the horn + back of the neck, which is meant to bleed off the frame.

HEAD = [
    (0, 260), (58, 155), (150, 95), (232, 148),
    (252, 255), (200, 335), (120, 348), (55, 320),
]

EAR = [(237, 118), (274, 90), (282, 140), (242, 156)]

HORN = [
    (150, 95),
    (175, 45), (220, 5), (285, -25), (360, -35), (430, -25), (490, 5),
    (535, 45), (560, 95), (565, 145),
    (555, 185), (530, 210),
    (490, 200), (445, 190), (400, 175), (350, 160), (300, 150), (255, 147),
    (232, 148),
]

EYE = [(112, 192), (126, 186), (132, 201), (120, 211), (106, 202)]
NOSTRIL = [(16, 250), (40, 242), (48, 265), (28, 278), (10, 266)]

SHAPES = [
    ("horn", HORN, (470, 60), 1.25, 1.0),
    ("ear", EAR, (470, 60), 1.1, 0.8),
    ("head", HEAD, (470, 60), 1.05, 0.6),
]

STOPS = [
    (0.00, (5, 8, 16)),
    (0.30, (11, 28, 66)),
    (0.55, (21, 58, 150)),
    (0.78, (54, 114, 245)),
    (1.00, (176, 209, 255)),
]

def lerp(a, b, t):
    return a + (b - a) * t

def color_at(t):
    t = max(0.0, min(1.0, t))
    for i in range(len(STOPS) - 1):
        t0, c0 = STOPS[i]
        t1, c1 = STOPS[i + 1]
        if t0 <= t <= t1:
            local = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            r = round(lerp(c0[0], c1[0], local))
            g = round(lerp(c0[1], c1[1], local))
            b = round(lerp(c0[2], c1[2], local))
            return f"rgb({r},{g},{b})"
    return f"rgb{STOPS[-1][1]}"

def poly_points_attr(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

def bbox_of(pts, margin=0):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)

def build_grid(bbox, spacing, jitter):
    x0, y0, x1, y1 = bbox
    cols = int((x1 - x0) / spacing) + 2
    rows = int((y1 - y0) / spacing) + 2
    grid = {}
    for j in range(rows):
        for i in range(cols):
            gx = x0 + i * spacing + random.uniform(-jitter, jitter)
            gy = y0 + j * spacing + random.uniform(-jitter, jitter)
            grid[(i, j)] = (gx, gy)
    return grid, cols, rows

def triangles(bbox, spacing=30, jitter=8):
    grid, cols, rows = build_grid(bbox, spacing, jitter)
    tris = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a, b, c, d = grid[(i, j)], grid[(i + 1, j)], grid[(i, j + 1)], grid[(i + 1, j + 1)]
            if random.random() < 0.5:
                tris.append((a, b, c))
                tris.append((b, d, c))
            else:
                tris.append((a, b, d))
                tris.append((a, d, c))
    return tris

def centroid(tri):
    return (sum(p[0] for p in tri) / 3, sum(p[1] for p in tri) / 3)

def render_facets(pts, light, gamma, brightness, maxd):
    bbox = bbox_of(pts, margin=20)
    tris = triangles(bbox)
    parts = []
    for tri in tris:
        cx, cy = centroid(tri)
        d = math.hypot(cx - light[0], cy - light[1])
        t = 1 - d / maxd
        t = max(0.0, min(1.0, t))
        t = t ** gamma
        t = t * brightness
        t += random.uniform(-0.03, 0.03)
        fill = color_at(t)
        parts.append(
            f'<polygon points="{poly_points_attr(tri)}" fill="{fill}" '
            f'stroke="#020509" stroke-opacity="0.35" stroke-width="0.55"/>'
        )
    return "\n".join(parts)

def outline_d(pts, close_x=0):
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f} "
    d += " ".join(f"L {x:.1f} {y:.1f}" for x, y in pts[1:])
    if close_x is not None:
        d += f" L {close_x} {pts[0][1]:.1f} Z"
    else:
        d += " Z"
    return d

def main():
    all_pts = HEAD + HORN + EAR
    full_bbox = bbox_of(all_pts, margin=50)
    maxd = math.hypot(full_bbox[2] - full_bbox[0], full_bbox[3] - full_bbox[1])

    defs = []
    layers = []
    for name, pts, light, gamma, brightness in SHAPES:
        d = outline_d(pts, close_x=None)
        defs.append(f'<clipPath id="clip-{name}"><path d="{d}"/></clipPath>')
        facets = render_facets(pts, light, gamma, brightness, maxd)
        stroke_op = 0.85 if name == "horn" else 0.55
        layers.append(f'''<g clip-path="url(#clip-{name})">{facets}</g>
<path d="{d}" fill="none" stroke="#4E8CFF" stroke-width="{2.2 if name=="horn" else 1.6}" stroke-linejoin="round" opacity="{stroke_op}" filter="url(#glow)"/>
<path d="{d}" fill="none" stroke="#DCE9FF" stroke-width="0.8" stroke-linejoin="round" opacity="0.4"/>''')

    eye_pts = poly_points_attr(EYE)
    nostril_pts = poly_points_attr(NOSTRIL)

    svg = f'''<svg viewBox="{full_bbox[0]:.0f} {full_bbox[1]:.0f} {full_bbox[2]-full_bbox[0]:.0f} {full_bbox[3]-full_bbox[1]:.0f}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Geometric water buffalo mark">
  <defs>
    {''.join(defs)}
    <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="7" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  {''.join(layers)}
  <polygon points="{eye_pts}" fill="#EAF2FF" opacity="0.95"/>
  <polygon points="{nostril_pts}" fill="#030609" opacity="0.6"/>
</svg>'''
    sys.stdout.write(svg)

if __name__ == "__main__":
    main()

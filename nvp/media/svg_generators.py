"""SVG generator module"""
import logging
import drawsvg as draw
import math

logger = logging.getLogger(__name__)


def to_px_size(value, ref_size):
    """convert a string to a pixel count"""
    if isinstance(value, str) and value.endswith("px"):
        val = float(value[:-2])
    elif isinstance(value, str) and value.endswith("%"):
        val = float(value[:-1]) * ref_size / 100.0
    else:
        val = float(value) * ref_size

    if val < 0.0:
        val = ref_size + val

    return int(val)


def generate_arrow(desc, img):
    """Generate an SVG arrow from a given description"""

    # Settings to draw an arrow:
    scale = desc["scale"]

    bh = desc["body_height"] * scale
    bw = desc["body_width"] * scale
    hh = desc["head_height"] * scale
    hw = desc["head_width"] * scale
    sw = desc["stroke_width"] * scale
    scol = desc["stroke_color"]
    fcol = desc["fill_color"]
    padx = desc["padding_x"]
    pady = desc["padding_y"]

    # First we need to figure out what should be the size of our layer image:
    size = desc["svg_size"]
    sww = padx * 2 + sw * 2 + bw + hw
    shh = pady * 2 + sw * 2 + max(bh, hh)

    if size == "auto":
        svg_width = sww
        svg_height = shh
    else:
        svg_width = to_px_size(size[0], img.width)
        svg_height = to_px_size(size[1], img.height)

    orig = desc["svg_origin"]
    orig_x = to_px_size(orig[0], svg_width)
    orig_y = to_px_size(orig[1], svg_height)

    # Start drawing:
    logger.info("Generating SVG of size %dx%d", svg_width, svg_height)

    drw = draw.Drawing(svg_width, svg_height, origin=(orig_x, orig_y))

    # Draw the path representing the arrow:
    # , transform=f"scale({scale})"
    p = draw.Path(stroke_width=sw, stroke=scol, fill=fcol)
    x0 = padx + sw
    cy = svg_height * 0.5

    p.M(x0, cy - bh * 0.5).L(x0 + bw, cy - bh * 0.5)
    p.L(x0 + bw, cy - hh * 0.5).L(x0 + bw + hw, cy)
    p.L(x0 + bw, cy + hh * 0.5)
    p.L(x0 + bw, cy + bh * 0.5).L(x0, cy + bh * 0.5).Z()

    drw.append(p)

    return drw


def generate_curved_arrow(desc, img):
    """Generate an SVG arrow from a given description"""

    # Settings to draw an arrow:
    scale = desc["scale"]

    bh = desc["body_height"] * scale
    bw = desc["body_width"] * scale
    hh = desc["head_height"] * scale
    hw = desc["head_width"] * scale
    sw = desc["stroke_width"] * scale
    scol = desc["stroke_color"]
    fcol = desc["fill_color"]
    padx = desc["padding_x"]
    pady = desc["padding_y"]

    # First we need to figure out what should be the size of our layer image:
    size = desc["svg_size"]
    sww = padx * 2 + sw * 2 + bw + hw
    shh = pady * 2 + sw * 2 + max(bh, hh) * 2

    if size == "auto":
        svg_width = sww
        svg_height = shh
    else:
        svg_width = to_px_size(size[0], img.width)
        svg_height = to_px_size(size[1], img.height)

    orig = desc["svg_origin"]
    orig_x = to_px_size(orig[0], svg_width)
    orig_y = to_px_size(orig[1], svg_height)

    # Start drawing:
    logger.info("Generating SVG of size %dx%d", svg_width, svg_height)

    drw = draw.Drawing(svg_width, svg_height, origin=(orig_x, orig_y))
    # drw = draw.Drawing(svg_width * 3, svg_height * 3, origin=(orig_x, orig_y))

    # Draw the path representing the arrow:
    # x0 = padx + sw
    cy = svg_height * 0.5

    p = draw.Path(stroke_width=sw, stroke=scol, fill=fcol, transform=f"rotate(38,{bh*0.5},{cy})")
    # p = draw.Path(stroke_width=sw, stroke=scol, fill=fcol)

    # compute sqrt of body width:
    sbw = bw / math.sqrt(2)

    r1 = sbw + bh * 0.5
    r2 = sbw - bh * 0.5
    dh = (hh - bh) * 0.5
    # cy = 0
    p.M(0, cy).A(r1, r1, 0, 0, 1, r1, cy - r1)
    p.L(r1, cy - r1 - dh).L(r1 + hw, cy - r1 + bh * 0.5).L(r1, cy - r1 + bh + dh)
    p.L(r1, cy - r1 + bh)
    p.A(r2, r2, 0, 0, 0, bh, cy)
    p.Z()

    drw.append(p)

    return drw


def generate_highlight_lines(desc, img):
    """Generate an SVG highlight lines for a given element"""

    # Retrieve the parameters
    scale = desc["scale"]
    size = desc["svg_size"]

    width = to_px_size(size[0], img.width) * scale
    height = to_px_size(size[1], img.height) * scale
    ratio = desc["ratio"]

    sw = desc["stroke_width"] * scale
    scol = desc["stroke_color"]

    padx = desc["padding_x"]
    pady = desc["padding_y"]
    x_steps = int(desc["num_x_steps"])
    y_steps = int(desc["num_y_steps"])

    # logger.info("highlight SVG size: %s x %s", width, height)

    drw = draw.Drawing(width, height, origin=(0, 0))

    ray_len = min(width, height) * ratio

    start_points = []

    dx = (width - 2 * padx) / (x_steps - 1)
    dy = (height - 2 * pady) / (y_steps - 1)

    for i in range(x_steps):
        start_points.append((padx + dx * i, pady))
        start_points.append((padx + dx * i, height - pady))

    for i in range(y_steps):
        start_points.append((padx, pady + dy * i))
        start_points.append((width - padx, pady + dy * i))

    p = draw.Path(stroke_width=sw, stroke=scol)

    for pt in start_points:
        # Compute a moving center location:
        if width > height:
            # interpolate in the xaxis:
            factor = pt[0] / width
            center = (height / 2.0 + (width - height) * factor, height / 2)
        else:
            factor = pt[1] / height
            center = (width / 2.0, width / 2 + (height - width) * factor)

        vec = [center[0] - pt[0], center[1] - pt[1]]
        dirlen = math.sqrt(vec[0] * vec[0] + vec[1] * vec[1])
        vec[0] *= ray_len / dirlen
        vec[1] *= ray_len / dirlen

        # logger.info("Drawing point from %s to %s", pt, epoint)
        p.M(pt[0], pt[1]).L(pt[0] + vec[0], pt[1] + vec[1])

    drw.append(p)

    return drw

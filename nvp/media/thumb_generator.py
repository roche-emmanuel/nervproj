"""ThumbGen handling component

This component is used to generate youtube thumbnails from a given description in yaml"""

import logging
import os
import drawsvg as draw

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import distance_transform_edt

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)

from rembg import new_session, remove


class ThumbGen(NVPComponent):
    """ThumbGen component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        # Storage for the currently loaded element templates:
        self.templates = {}
        self.parameters = {}

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "drawsvg-test":
            return self.drawsvg_test()

        if cmd == "gen-thumb":
            tagname = self.get_param("tag_name")

            # Get the desc dir:
            desc_dir = os.environ["NV_YT_DESC_DIR"]

            # Load the common templates/parameters:
            common_file = self.get_path(desc_dir, "common.yml")
            if self.file_exists(common_file):
                logger.info("Loading common templates...")
                self.load_templates(common_file)

            # get the prefix:
            prefix = tagname[:3]
            # cfg_file = self.get_path(self.get_cwd(), "descs", prefix, tagname + ".yml")
            cfg_file = self.get_path(desc_dir, prefix, tagname + ".yml")
            cfg = self.read_yaml(cfg_file)

            # Get the entry from the file:
            desc = cfg["thumbnail"]
            return self.generate_thumbnail(tagname, desc)

        if cmd == "remove-bg":
            in_file = self.get_param("input_file")

            model = self.get_param("model_name")
            min_dist = self.get_param("min_dist")
            max_dist = self.get_param("max_dist")
            bg_color = self.get_param("bg_color")
            contour_size = self.get_param("contour_size")
            contour_color = self.get_param("contour_color")

            if in_file == "all":
                # iterate on all image files:
                cur_dir = self.get_cwd()

                out_dir = self.get_param("out_dir")
                self.make_folder(out_dir)
                all_files = self.get_all_files(cur_dir, recursive=False)
                exts = [".png", ".jpeg", ".jpg"]

                for fname in all_files:
                    ext = self.get_path_extension(fname).lower()
                    if ext not in exts:
                        continue

                    # Check if we already have the text file:
                    src_file = self.get_path(cur_dir, fname)
                    # out_file = self.set_path_extension(fname, "_nobg.png")
                    out_file = self.set_path_extension(fname, ".png")
                    out_file = self.get_path(out_dir, out_file)

                    if self.file_exists(out_file):
                        continue

                    # Otherwise we process this file:
                    self.remove_background(
                        src_file, out_file, model, min_dist, max_dist, bg_color, contour_size, contour_color
                    )

                return True
            else:
                out_file = self.get_param("output_file")
                return self.remove_background(
                    in_file, out_file, model, min_dist, max_dist, bg_color, contour_size, contour_color
                )

        return False

    def load_templates(self, tpl_file):
        """Load the templates from a given file"""
        if not self.file_exists(tpl_file):
            logger.warning("Missing template file %s", tpl_file)

        cfg = self.read_yaml(tpl_file)

        # override any parameter:
        params = cfg.get("parameters", {})
        for key, val in params.items():
            self.parameters[key] = val

        # override/extend any templates:
        tpls = cfg.get("templates", {})

        for key, tpl in tpls.items():
            if key not in self.templates:
                self.templates[key] = tpl
            else:
                basetpl = self.templates[key]
                for ename, entry in tpl.items():
                    basetpl[ename] = entry

    def drawsvg_test(self):
        """Test function for drawsvg"""
        logger.info("Should perform drawsvg test here.")

        d = draw.Drawing(
            400,
            200,
            origin="center",
            animation_config=draw.types.SyncedAnimationConfig(
                # Animation configuration
                duration=8,  # Seconds
                show_playback_progress=True,
                show_playback_controls=True,
            ),
        )
        d.append(draw.Rectangle(-200, -100, 400, 200, fill="#eee"))  # Background
        d.append(draw.Circle(0, 0, 40, fill="green"))  # Center circle

        # Animation
        circle = draw.Circle(0, 0, 0, fill="gray")  # Moving circle
        circle.add_key_frame(0, cx=-100, cy=0, r=0)
        circle.add_key_frame(2, cx=0, cy=-100, r=40)
        circle.add_key_frame(4, cx=100, cy=0, r=0)
        circle.add_key_frame(6, cx=0, cy=100, r=40)
        circle.add_key_frame(8, cx=-100, cy=0, r=0)
        d.append(circle)
        r = draw.Rectangle(0, 0, 0, 0, fill="silver")  # Moving square
        r.add_key_frame(0, x=-100, y=0, width=0, height=0)
        r.add_key_frame(2, x=0 - 20, y=-100 - 20, width=40, height=40)
        r.add_key_frame(4, x=100, y=0, width=0, height=0)
        r.add_key_frame(6, x=0 - 20, y=100 - 20, width=40, height=40)
        r.add_key_frame(8, x=-100, y=0, width=0, height=0)
        d.append(r)

        # Changing text
        draw.native_animation.animate_text_sequence(
            d, [0, 2, 4, 6], ["0", "1", "2", "3"], 30, 0, 1, fill="yellow", center=True
        )

        # Save as a standalone animated SVG or HTML
        # d.save_svg('playback-controls.svg')
        # d.save_html('playback-controls.html')

        # Display in Jupyter notebook
        # d.display_image()  # Display SVG as an image (will not be interactive)
        # d.display_iframe()  # Display as interactive SVG (alternative)
        # d.as_gif('orbit.gif', fps=10)  # Render as a GIF image, optionally save to file
        d.as_mp4("orbit.mp4", fps=60, verbose=True)  # Render as an MP4 video, optionally save to file
        # d.as_spritesheet('orbit-spritesheet.png', row_length=10, fps=3)  # Render as a spritesheet
        # d.display_inline()  # Display as interactive SVG
        logger.info("Generation done.")

        return True

    def compute_distance_to_foreground(self, img):
        """Compute the euclidian distance to the 1 elements assuming that 1 is for the forreground"""
        arr = np.array(img)

        binary_arr = np.zeros_like(arr)
        binary_arr[arr < 200] = 1

        # arr.astype(np.bool_).astype(np.uint8)

        # flip 0/1:
        # binary_arr = 1 - binary_arr

        dist = distance_transform_edt(binary_arr)
        return dist

    def update_bg_color(self, arr, bg_color):
        """Replace the background color"""

        col = [np.float32(el) / 255.0 for el in bg_color.split(",")]
        arr = arr.astype(np.float32) / 255.0
        colarr = np.zeros_like(arr)
        alpha = arr[:, :, 3]

        for i in range(4):
            colarr[:, :, i] = col[i]

            arr[:, :, i] = arr[:, :, i] * alpha + colarr[:, :, i] * (1.0 - alpha)

        arr = (arr * 255.0).astype(np.uint8)

        return arr

    def apply_contour(self, arr, mask, dist, contour_size, contour_color):
        """Apply a contour around the target object"""
        col = [np.float32(el) / 255.0 for el in contour_color.split(",")]
        logger.info("Applying contour of size %f, with color %s", contour_size, contour_color)

        img_arr = arr.astype(np.float32) / 255.0

        # Prepare the result image:
        res = np.copy(img_arr)

        # Fill with the contour color:
        idx = dist <= contour_size
        alpha = np.array(mask).astype(np.float32) / 255.0

        for i in range(4):
            # Fill with the contour color:
            res[idx, i] = col[i]
            # Re-add the subject on top of contour:
            res[:, :, i] = img_arr[:, :, i] * alpha + res[:, :, i] * (1.0 - alpha)

        return (res * 255.0).astype(np.uint8)

    def remove_background(
        self, in_file, out_file, model_name, min_dist, max_dist, bg_color, contour_size, contour_color
    ):
        """Remove the background from an image file"""
        # Usage infos: https://github.com/roche-emmanuel/rembg/blob/main/USAGE.md

        if out_file is None:
            out_file = self.set_path_extension(in_file, "_nobg.png")

        logger.info("Removing background from %s...", in_file)
        input_img = Image.open(in_file)
        # output_img = remove(input_img)

        # model_name = "u2net"
        # model_name = "isnet-general-use"
        session = new_session(model_name)
        # Get the mask only:
        mask = remove(input_img, session=session, only_mask=True).convert("L")
        logger.info("Retrieved foreground mask.")

        # Convert the input image to RGBA:
        img = input_img.convert("RGBA")
        img_arr = np.array(img)

        # Compute the distance to foreground:
        dist = self.compute_distance_to_foreground(mask)

        # if a contour size is provided the we apply it here:
        if contour_size > 0:
            img_arr = self.apply_contour(img_arr, mask, dist, contour_size, contour_color)

        if max_dist != min_dist:

            dist = np.clip(dist, min_dist, max_dist)
            alpha = 1.0 - (dist - min_dist) / (max_dist - min_dist)

            img_arr[:, :, 3] = (255 * alpha).astype(np.uint8)

        else:
            # Use default processing:
            img_arr[:, :, 3] = mask

        if bg_color is not None:
            img_arr = self.update_bg_color(img_arr, bg_color)

        # Convert the numpy array back to image:
        output_img = Image.fromarray(img_arr)
        output_img.save(out_file)

        logger.info("Done removing background.")
        return True

    def load_background_image(self, iname):
        """Load a background image"""

        bg_dir = self.get_path(self.get_cwd(), "inputs", "backgrounds")

        ext = self.get_path_extension(iname)
        exts = [".jpg", ".png"]
        if ext == "":
            for ext in exts:
                if self.file_exists(bg_dir, iname + ext):
                    iname = iname + ext
                    break

        # The file should exist:
        self.check(self.file_exists(bg_dir, iname), "Invalid background image %s", iname)

        # load that image:
        img = Image.open(self.get_path(bg_dir, iname))
        return img

    def adjust_tint(self, image, tint_factors):
        """Adjust the tint of an image"""
        # Split the image into its individual color channels (R, G, B)
        r, g, b, a = image.split()

        # Reduce the intensity of the red channel using the tint_factor
        r = r.point(lambda i: i * tint_factors[0])
        g = g.point(lambda i: i * tint_factors[1])
        b = b.point(lambda i: i * tint_factors[2])

        # Merge the adjusted color channels back into a single image
        adjusted_image = Image.merge("RGBA", (r, g, b, a))

        return adjusted_image

    def adjust_brightness(self, image, factor):
        """Adjust the tint of an image"""
        # Create a lambda function to adjust the pixel values
        adjust = lambda value: min(int(value * factor), 255)

        r, g, b, a = image.split()
        r = r.point(adjust)
        g = g.point(adjust)
        b = b.point(adjust)

        # Merge the adjusted color channels back into a single image
        return Image.merge("RGBA", (r, g, b, a))

    def mirror_image_horiz(self, img):
        """Mirror an image horizontally"""
        return img.transpose(Image.FLIP_LEFT_RIGHT)

    def apply_outline(self, sub_img, contour_size, contour_color):
        """Apply the outline"""

        sub_arr = np.array(sub_img)
        mask = sub_arr[:, :, 3]
        col = [np.float32(el) / 255.0 for el in contour_color]

        # Compute the distance to foreground:
        dist = self.compute_distance_to_foreground(mask)

        img_arr = sub_arr.astype(np.float32) / 255.0

        # Prepare the result image:
        res = np.copy(img_arr)

        # Fill with the contour color:
        idx = dist <= contour_size
        alpha = np.array(mask).astype(np.float32) / 255.0

        for i in range(4):
            # Fill with the contour color:
            res[idx, i] = col[i]
            # Re-add the subject on top of contour:
            res[:, :, i] = img_arr[:, :, i] * alpha + res[:, :, i] * (1.0 - alpha)

        sub_arr = (res * 255.0).astype(np.uint8)

        return Image.fromarray(sub_arr)

    def add_image_layer(self, img, desc):
        """Add a sub image"""
        img_dir = self.get_path(self.get_cwd(), "inputs")

        width = img.width
        height = img.height
        ref_size = min(width, height)

        logger.info("Adding sub image: %s", desc["src"])

        # load the image from source:
        sub_img = Image.open(self.get_path(img_dir, desc["src"]))
        sub_img = sub_img.convert("RGBA")

        # Rescale the image to fit the requested scale:
        tgt_size = ref_size * desc["scale"]

        # compute the scaling factor:
        sfactor = min(tgt_size / sub_img.width, tgt_size / sub_img.height)

        # Resize the image sub_img to the "tgt_size" value keeping the aspect ratio:
        sub_img = sub_img.resize((int(sub_img.width * sfactor), int(sub_img.height * sfactor)))

        return sub_img

    def to_px_size(self, value, ref_size):
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

    def add_text_layer(self, img, desc):
        """Add a text layer"""

        font_file = self.get_path(self.get_input_dir(), "fonts", desc.get("font", "BebasNeue.otf"))
        self.check(self.file_exists(font_file), "Invalid font file %s", font_file)

        # Specify the font style, size, and color
        # font = ImageFont.truetype("arial.ttf", 72)  # Replace "arial.ttf" with the path to your font file
        font = ImageFont.truetype(font_file, desc.get("font_size", 160))

        line_spacing = desc.get("line_spacing", 10.0)

        lines = desc["text"].split("\n")
        nlines = len(lines)
        max_width = 0
        tot_height = 0
        text_heights = []
        for line in lines:
            text_width, text_height = self.get_text_dimensions(line, font)
            text_width = int(text_width)
            text_height = int(text_height)
            max_width = max(max_width, text_width)
            text_heights.append(text_height)
            tot_height += text_height

        if len(lines) > 1:
            tot_height += line_spacing * (nlines - 1)
        tot_height = int(tot_height)

        outline_width = desc.get("outline_width", 5)

        # We also need to take into account the outline_width for the total size of the sub image:
        tot_height += int(2 * outline_width)
        max_width += int(outline_width)

        # Also check if we should take into account a rect padding:
        hpad = self.to_px_size(desc.get("hpad", 0), max_width)
        vpad = self.to_px_size(desc.get("vpad", 0), tot_height)

        max_width += int(2 * hpad)
        tot_height += int(2 * vpad)

        outline_color = desc.get("outline_color", (255, 0, 0, 255))
        text_color = desc.get("color", (255, 255, 255, 255))
        text_halign = desc.get("halign", "left")
        rect_color = desc.get("rect_color", (0, 0, 0, 0))
        shadow = desc.get("shadow_offset", [0, 0])
        xoff = int(shadow[0])
        yoff = int(shadow[1])
        shadow_color = desc.get("shadow_color", (0, 0, 0, 128))

        if isinstance(rect_color, list):
            rect_color = tuple(rect_color)
        if isinstance(text_color, list):
            text_color = tuple(text_color)
        if isinstance(outline_color, list):
            outline_color = tuple(outline_color)

        sub_img = Image.new("RGBA", (max_width, tot_height))
        draw = ImageDraw.Draw(sub_img)

        draw.rectangle([(0, 0), (sub_img.width, sub_img.height)], fill=rect_color)

        if desc.get("hide_text", False) is False:
            anchor = "lt"
            # x = outline_width
            x = hpad
            y = vpad + outline_width

            if text_halign == "center":
                x = sub_img.width // 2
                anchor = "mt"
            if text_halign == "right":
                x = sub_img.width - hpad - outline_width
                anchor = "rt"

            for idx, line in enumerate(lines):
                if xoff != 0 or xoff != 0:
                    # draw the shadow first:
                    draw.text(
                        (x + xoff, y + yoff),
                        line,
                        font=font,
                        fill=shadow_color,
                        stroke_width=0,
                        stroke_fill=None,
                        anchor=anchor,
                    )

                draw.text(
                    (x, y),
                    line,
                    font=font,
                    fill=text_color,
                    stroke_width=outline_width,
                    stroke_fill=outline_color,
                    anchor=anchor,
                )
                y += text_heights[idx] + line_spacing

        return sub_img

    def apply_anchor_offset(self, anchor, xpos, ypos, sww, shh, hpad, vpad):
        """Apply an anchor offset"""
        if anchor == "cc":
            return xpos - sww // 2, ypos - shh // 2

        if anchor == "tl":
            return xpos, ypos
        if anchor == "dtl":
            return xpos - hpad, ypos - vpad
        if anchor == "tr":
            return xpos - sww, ypos
        if anchor == "dtr":
            return xpos - sww + hpad, ypos - vpad
        if anchor == "bl":
            return xpos, ypos - shh
        if anchor == "dbl":
            return xpos - hpad, ypos + vpad - shh
        if anchor == "br":
            return xpos - sww, ypos - shh
        if anchor == "dbr":
            return xpos - sww + hpad, ypos + vpad - shh

    def add_element(self, img, desc):
        """Add a single element to the image"""
        if "src" in desc:
            layer = self.add_image_layer(img, desc)
            anchor = desc.get("anchor", "cc")
        elif "text" in desc:
            layer = self.add_text_layer(img, desc)
            anchor = desc.get("anchor", "tl")
        else:
            self.throw("Unknown layer type: %s", desc)

        if "tint_factors" in desc:
            layer = self.adjust_tint(layer, desc["tint_factors"])

        if "brightness" in desc:
            layer = self.adjust_brightness(layer, desc["brightness"])

        if desc.get("mirror", False):
            layer = self.mirror_image_horiz(layer)

        if "outline_size" in desc:
            contour_size = desc["outline_size"]
            contour_color = desc["outline_color"]
            layer = self.apply_outline(layer, contour_size, contour_color)

        if "angle" in desc:
            layer = layer.rotate(desc["angle"], expand=True)

        # Compute center position:
        sww = layer.width
        shh = layer.height
        width = img.width
        height = img.height

        xpos = self.to_px_size(desc["pos"][0], width)
        ypos = self.to_px_size(desc["pos"][1], height)
        hpad = self.to_px_size(desc.get("hpad", 0), sww)
        vpad = self.to_px_size(desc.get("vpad", 0), shh)

        # xpos = desc["pos"][0]
        # if isinstance(xpos, str) and xpos.endswith("px"):
        #     xpos = int(xpos[:-2])
        # else:
        #     xpos = int(xpos * width)

        # ypos = desc["pos"][1]
        # if isinstance(ypos, str) and ypos.endswith("px"):
        #     ypos = int(ypos[:-2])
        # else:
        #     ypos = int(ypos * height)

        # if xpos < 0:
        #     xpos = width + xpos
        # if ypos < 0:
        #     ypos = height + ypos

        xpos, ypos = self.apply_anchor_offset(anchor, xpos, ypos, sww, shh, hpad, vpad)

        img.paste(layer, (xpos, ypos), mask=layer)

        return img

    def inject_base(self, desc):
        """Check if there is a base in our description and inject it in that case"""

        if "base" not in desc:
            return desc

        # remove the base element from the desc now:
        bname = desc.pop("base")

        # get the template with that name
        tpl = self.inject_base(self.templates[bname])

        for key, val in tpl.items():
            if key not in desc:
                desc[key] = val

        return desc

    def add_elements(self, img_arr, elems):
        """Add "sub-images" on our background image"""
        img = Image.fromarray((img_arr * 255.0).astype(np.uint8))

        for desc in elems:

            # For each element, we check if we have a base:
            desc = self.inject_base(desc)
            img = self.add_element(img, desc)

        return np.array(img).astype(np.float32) / 255.0

    def fill_area(self, img, width, height):
        """Stretch the input image as needed to fill a given area"""

        # Calculate the aspect ratios
        original_width, original_height = img.size
        target_width, target_height = width, height
        width_ratio = target_width / original_width
        height_ratio = target_height / original_height

        # Determine the resize ratio and apply it to the image
        resize_ratio = max(width_ratio, height_ratio)
        new_size = (int(original_width * resize_ratio), int(original_height * resize_ratio))
        resized_image = img.resize(new_size)

        # Create a blank canvas of size 1280x720
        canvas = Image.new("RGBA", (target_width, target_height), "white")

        # Calculate the position to center the resized image on the canvas
        x_offset = (target_width - new_size[0]) // 2
        y_offset = (target_height - new_size[1]) // 2

        # Paste the resized image onto the canvas
        canvas.paste(resized_image, (x_offset, y_offset))

        return canvas

    def get_input_dir(self):
        """Retrieve the input dir"""
        return self.get_path(self.get_cwd(), "inputs")

    def draw_subtitle(self, img_arr, desc, drawbg):
        """Draw the subtitle of the thumbnail if applicable"""

        fname = "subtitle"
        if fname not in desc:
            # Nothing to do:
            return img_arr

        params = {
            "text": desc[fname],
            "font_file": desc.get(f"{fname}_font", "Doctor Glitch.otf"),
            "font_size": desc.get(f"{fname}_font_size", 56),
            "text_color": desc.get(f"{fname}_color", (255, 255, 255, 255)),
            "rect_color": desc.get(f"{fname}_rect_color", (130, 130, 130, 220)),
            "rect_hpad": desc.get(f"{fname}_rect_hpad", 20),
            "outline_width": desc.get(f"{fname}_outline_size", 4),
            "outline_color": desc.get(f"{fname}_outline_color", (0, 0, 0, 200)),
            "xpos": desc.get(f"{fname}_xpos", 20),
            "ypos": desc.get(f"{fname}_ypos", -40),
            "line_spacing": desc.get(f"{fname}_line_spacing", 10),
            "text_halign": desc.get(f"{fname}_halign", "left"),
            "shadow_offset_x": 8,
            "shadow_offset_y": 8,
        }

        return self.draw_text_overlay(img_arr, params, drawbg)

    def draw_title(self, img_arr, desc, drawbg):
        """Draw the title elements"""

        fname = "title"

        if fname not in desc:
            # Nothing to do:
            return img_arr

        params = {
            "text": desc[fname],
            "font_file": desc.get(f"{fname}_font", "BebasNeue.otf"),
            "font_size": desc.get(f"{fname}_font_size", 160),
            "text_color": desc.get(f"{fname}_color", (255, 255, 0, 255)),
            "rect_color": desc.get(f"{fname}_rect_color", (230, 230, 230, 80)),
            "rect_hpad": desc.get(f"{fname}_rect_hpad", 30),
            "outline_width": desc.get(f"{fname}_outline_size", 5),
            "outline_color": desc.get(f"{fname}_outline_color", (255, 0, 0, 200)),
            "xpos": desc.get(f"{fname}_xpos", 20),
            "ypos": desc.get(f"{fname}_ypos", 40),
            "line_spacing": desc.get(f"{fname}_line_spacing", 10),
            "text_halign": desc.get(f"{fname}_halign", "left"),
            "shadow_offset_x": 0,
            "shadow_offset_y": 0,
        }

        return self.draw_text_overlay(img_arr, params, drawbg)

    def get_text_dimensions(self, text_string, font):
        """Get the dimensions of a text"""
        # https://stackoverflow.com/a/46220683/9263761
        # ascent, descent = font.getmetrics()
        # logger.info("ascent: %f, descent: %f", ascent, descent)

        text_width = font.getmask(text_string).getbbox()[2]
        # text_height = font.getmask(text_string).getbbox()[3]
        text_height = font.getmask(text_string).getbbox()[3]
        # logger.info("text_height: %f", text_height)

        return (text_width, text_height)

    def draw_text_overlay(self, img_arr, params, drawbg):
        """Draw a text overlay on the image with an optional background band and outline effect."""

        width = img_arr.shape[1]
        height = img_arr.shape[0]

        # overlay = Image.new("RGBA", img.size)
        overlay = Image.new("RGBA", (width, height))

        # Create an ImageDraw object
        draw = ImageDraw.Draw(overlay)

        text = params["text"]
        font_file = self.get_path(self.get_input_dir(), "fonts", params["font_file"])
        self.check(self.file_exists(font_file), "Invalid font file %s", font_file)

        # Specify the font style, size, and color
        # font = ImageFont.truetype("arial.ttf", 72)  # Replace "arial.ttf" with the path to your font file
        font = ImageFont.truetype(font_file, params["font_size"])  # Replace "arial.ttf" with the path to your font file

        # Calculate the position to center the text on the image

        # text_width, text_height = draw.textsize(text, font)
        _, text_height = self.get_text_dimensions(text, font)
        # text_bbox = draw.textbbox((0, 0), text, font=font)
        # text_width = text_bbox[2]
        # - text_bbox[0]
        # text_height = text_bbox[3]
        # - text_bbox[1]

        # Draw the background rectangle:
        x = params["xpos"]
        y = params["ypos"]
        line_spacing = params["line_spacing"]

        lines = text.split("\n")
        nlines = len(lines)
        total_text_height = text_height * nlines + line_spacing * (nlines - 1)
        hpad = params["rect_hpad"]
        rect_color = params["rect_color"]
        outline_width = params["outline_width"]
        outline_color = params["outline_color"]
        text_color = params["text_color"]
        text_halign = params["text_halign"]

        if isinstance(rect_color, list):
            rect_color = tuple(rect_color)
        if isinstance(text_color, list):
            text_color = tuple(text_color)
        if isinstance(outline_color, list):
            outline_color = tuple(outline_color)

        rect_height = 2 * hpad + total_text_height

        if y < 0:
            y = height + y - total_text_height

        if drawbg:
            draw.rectangle([(0, y - hpad), (width, y - hpad + rect_height)], fill=rect_color)
        else:
            anchor = "lt"

            if text_halign == "center":
                x = width // 2
                anchor = "mt"
            if text_halign == "right":
                x = width - x
                anchor = "rt"

            # x = (width - text_width) // 2
            # y = (height - text_height) // 2

            # Draw the text outline if applicable:

            # if outline_width > 0:
            #     outline_color = params["outline_color"]

            #     for xo in range(-outline_width, outline_width + 1):
            #         for yo in range(-outline_width, outline_width + 1):
            #             draw.text((x + xo, y + yo), text, font=font, fill=outline_color)

            # Write the text on the image
            # Split the text lines:

            xoff = params["shadow_offset_x"]
            yoff = params["shadow_offset_y"]
            shadow_color = (0, 0, 0, 128)

            for line in lines:
                if xoff != 0 or xoff != 0:
                    # draw the shadow first:
                    draw.text(
                        (x + xoff, y + yoff),
                        line,
                        font=font,
                        fill=shadow_color,
                        stroke_width=0,
                        stroke_fill=None,
                        anchor=anchor,
                    )

                draw.text(
                    (x, y),
                    line,
                    font=font,
                    fill=text_color,
                    stroke_width=outline_width,
                    stroke_fill=outline_color,
                    anchor=anchor,
                )
                y += text_height + line_spacing

        ov_arr = np.array(overlay).astype(np.float32) / 255.0

        # Composite the images:
        # img.alpha_composite(overlay)
        alpha = ov_arr[:, :, 3]
        for i in range(3):
            img_arr[:, :, i] = img_arr[:, :, i] * (1.0 - alpha) + ov_arr[:, :, i] * alpha

        # return Image.fromarray((img_arr * 255.0).astype(np.uint8))
        return img_arr

    def generate_thumbnail(self, tagname, desc):
        """This function is used to generate a thumbnail with the given input settings"""

        # Thumbnail dimensions:
        width = 1280
        height = 720

        # logger.info("Input desc: %s", desc)

        # Get the input/output dir:
        out_dir = self.get_path(self.get_cwd(), "outputs")
        self.make_folder(out_dir)

        # write an output file in the output dir:
        out_file = self.get_path(out_dir, f"{tagname}.png")

        # Check if we have a background image:
        if "background" in desc:
            # load the background image:
            img = self.load_background_image(desc["background"])
        else:
            # Create a completely back image:
            img = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        img = self.fill_area(img, width, height)

        arr = np.array(img).astype(np.float32) / 255.0

        # First we draw the background rects:
        if "title" in desc:
            arr = self.draw_title(arr, desc, True)

        if "subtitle" in desc:
            arr = self.draw_subtitle(arr, desc, True)

        # Add the additional elements:
        elems = None
        if "elements" in desc:
            elems = desc["elements"]
        elif "images" in desc:
            elems = desc["images"]

        if elems is not None:
            arr = self.add_elements(arr, elems)

        # Write the title if any:
        if "title" in desc:
            arr = self.draw_title(arr, desc, False)

        # Write the subtile if any:
        if "subtitle" in desc:
            arr = self.draw_subtitle(arr, desc, False)

        # save the image:
        # img = Image.fromarray(arr)
        img = Image.fromarray((arr * 255.0).astype(np.uint8))

        logger.info("Writing thumbnail: %s", out_file)
        img.save(out_file, "PNG")

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("ThumbGen", ThumbGen(context))

    psr = context.build_parser("gen-thumb")
    # psr.add_flag("-f", "--use-folder-name", dest="use_folder_name")("Rename using parent folder name")
    # psr.add_str("tag_name", nargs="?", default="all")("input file where to read the config settings from")
    psr.add_str("tag_name")("Input tag to generate a thumbnail for")
    psr.add_str("-i", "--input", dest="input_file", default="videos.yml")(
        "input file where to read the config settings from"
    )

    psr = context.build_parser("remove-bg")
    psr.add_str("-i", "--input", dest="input_file", default="all")(
        "input image file from which to remove the background"
    )
    psr.add_str("-o", "--output", dest="output_file")("output image file")
    psr.add_str("-m", "--model", dest="model_name", default="u2net")("Name of model to use")
    psr.add_float("--mind", dest="min_dist", default=0.0)("Min falloff dist")
    psr.add_float("--maxd", dest="max_dist", default=0.0)("Max falloff dist")
    psr.add_str("--bgcolor", dest="bg_color")("Background color as coma separated list of U8s")
    psr.add_str("--out-dir", dest="out_dir", default="nobg")("Output directory")
    psr.add_str("--ctcolor", dest="contour_color", default="255,255,255,255")("Contour color")
    psr.add_float("--ctsize", dest="contour_size", default=0.0)("Contour size")

    psr = context.build_parser("drawsvg-test")

    comp.run()

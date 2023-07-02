"""In this module we define the styles used in the CV builder"""


from odf.style import (
    GraphicProperties,
    ParagraphProperties,
    TableCellProperties,
    TableColumnProperties,
    TableProperties,
    TableRowProperties,
    TextProperties,
)


def define_cv_styles(self):
    """Define the styles"""

    loextns = "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0"

    style = self.add_paragraph_style("VerticalCenterStyle")
    style.addElement(ParagraphProperties(verticalalign="center"))

    style = self.add_graphic_style("GraphicsBase")
    style.addElement(
        GraphicProperties(
            anchortype="paragraph",
            x="0cm",
            y="0cm",
            wrap="dynamic",
            numberwrappedparagraphs="nolimit",
            wrapcontour="false",
            verticalpos="top",
            verticalrel="paragraph",
            horizontalpos="center",
            horizontalrel="paragraph",
        )
    )

    style = self.add_graphic_style("PhotoStyle", parentstylename="GraphicsBase")
    style.addElement(
        GraphicProperties(
            wrap="none",
            runthrough="foreground",
            verticalpos="middle",
            verticalrel="paragraph-content",
            horizontalpos="center",
            horizontalrel="paragraph-content",
            mirror="none",
            clip="rect(0cm, 0cm, 0cm, 0cm)",
            luminance="0%",
            contrast="0%",
            red="0%",
            green="0%",
            blue="0%",
            gamma="100%",
            colorinversion="false",
            imageopacity="100%",
            colormode="standard",
        )
    )

    style = self.add_auto_graphic_style("LineStyle")
    style.addElement(
        GraphicProperties(
            wrap="none",
            runthrough="background",
            strokewidth="0.035cm",
            flowwithtext="false",
            # allowoverlap="true",
            markerstartwidth="0.5cm",
            markerendwidth="0.5cm",
            strokecolor=self.rgb_to_hex(self.colors["highlight"]),
            paddingtop="0.018cm",
            paddingbottom="0.018cm",
            paddingleft="0.018cm",
            paddingright="0.018cm",
            wrapinfluenceonposition="once-concurrent",
            verticalpos="bottom",
            verticalrel="text",
            horizontalpos="from-left",
            horizontalrel="paragraph",
        )
    )

    style = self.add_graphic_style("InlinePhotoStyle", parentstylename="PhotoStyle")
    style.addElement(
        GraphicProperties(
            wrap="parallel",
            wrapcontour="false",
            verticalpos="middle",
            verticalrel="text",
            horizontalpos="from-left",
        )
    )

    style = self.add_paragraph_style("FirstNameStyle")
    style.addElement(ParagraphProperties(textalign="center", verticalalign="center"))
    style.addElement(
        TextProperties(fontsize="32pt", fontweight="normal", fontname="Roboto Condensed", fontfamily="Roboto Condensed")
    )

    style = self.add_text_style("LastNameStyle")
    style.addElement(
        TextProperties(
            fontsize="32pt",
            fontweight="normal",
            fontname="Roboto",
            fontfamily="Roboto",
            color=self.rgb_to_hex(self.colors["highlight"]),
        )
    )

    style = self.add_text_style("ApplyHeaderStyle")
    style.addElement(
        TextProperties(
            fontweight="bold",
            color=self.rgb_to_hex(self.colors["highlight"]),
        )
    )

    style = self.add_paragraph_style("QualificationsStyle")
    style.addElement(
        ParagraphProperties(textalign="center", margintop="0cm", marginbottom="0.2cm", verticalalign="center")
    )
    style.addElement(
        TextProperties(
            fontsize="7.6pt",
            fontweight="normal",
            fontname="Source Sans Pro",
            fontfamily="Source Sans Pro",
            color=self.rgb_to_hex(self.colors["highlight"]),
            # texttransform="uppercase",
            fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("JobTitlePlaceHolderStyle")
    style.addElement(
        ParagraphProperties(textalign="center", margintop="0.15cm", marginbottom="0.38cm", verticalalign="center")
    )

    style = self.add_paragraph_style("SkillCatStyle")
    style.addElement(
        ParagraphProperties(textalign="center", margintop="0.2cm", marginbottom="0.05cm", verticalalign="center")
    )
    style.addElement(
        TextProperties(
            fontsize="9pt",
            fontweight="bold",
            fontname="Roboto Condensed",
            fontfamily="Roboto Condensed",
            color=self.rgb_to_hex(self.colors["highlight"]),
            # texttransform="uppercase",
            fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("JobStyle")
    style.addElement(
        ParagraphProperties(textalign="center", margintop="0.15cm", marginbottom="0.15cm", verticalalign="center")
    )
    props = TextProperties(
        fontsize="9.5pt",
        fontweight="bold",
        fontname="Source Sans Pro",
        fontfamily="Source Sans Pro",
        color=self.rgb_to_hex(self.colors["darktext"]),
        # texttransform="uppercase",
        backgroundcolor=self.rgb_to_hex(self.colors["darktext"], lighten=0.9),
        fontvariant="small-caps",
    )
    style.addElement(props)

    props.setAttrNS(loextns, "char-shading-value", "0")
    props.setAttrNS(loextns, "padding-left", "1.2cm")
    props.setAttrNS(loextns, "padding-right", "1.2cm")
    props.setAttrNS(loextns, "padding-top", "0.05cm")
    props.setAttrNS(loextns, "padding-bottom", "0.05cm")
    props.setAttrNS(loextns, "border", "1.5pt solid " + self.rgb_to_hex(self.colors["darktext"], lighten=0.3))
    props.setAttrNS(loextns, "shadow", "3pt 3pt")

    style = self.add_paragraph_style("MissionProjectStyle")
    style.addElement(
        ParagraphProperties(textalign="left", margintop="0cm", marginbottom="0.2cm", verticalalign="center")
    )
    style.addElement(
        TextProperties(
            fontsize="9pt",
            fontweight="bold",
            fontname="Roboto Condensed",
            fontfamily="Roboto Condensed",
            color=self.rgb_to_hex(self.colors["highlight"]),
            # texttransform="uppercase",
            fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("MissionPositionStyle")
    style.addElement(
        ParagraphProperties(
            textalign="right", margintop="0cm", marginright="0.08cm", marginbottom="0.2cm", verticalalign="center"
        )
    )
    style.addElement(
        TextProperties(
            fontsize="9pt",
            fontweight="bold",
            fontname="Roboto Condensed",
            fontfamily="Roboto Condensed",
            color=self.rgb_to_hex(self.colors["highlight"], lighten=0.1),
            textshadow="1pt 1pt",
            # texttransform="uppercase",
            # fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("MissionDateStyle")
    style.addElement(
        ParagraphProperties(
            textalign="right", margintop="0cm", marginbottom="0.cm", marginright="0.3cm", verticalalign="center"
        )
    )
    style.addElement(
        TextProperties(
            fontsize="7pt",
            fontweight="normal",
            fontname="Calibri",
            fontfamily="Calibri",
            color=self.rgb_to_hex(self.colors["highlight"]),
            fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("MissionClientStyle")
    style.addElement(
        ParagraphProperties(
            textalign="right", margintop="0.1cm", marginbottom="0.cm", marginright="0.3cm", verticalalign="center"
        )
    )
    style.addElement(
        TextProperties(
            fontsize="7pt",
            fontweight="bold",
            fontname="Calibri",
            fontfamily="Calibri",
            color=self.rgb_to_hex(self.colors["darktext"]),
            # fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("AddressStyle")
    style.addElement(
        ParagraphProperties(textalign="center", margintop="0cm", marginbottom="0.2cm", verticalalign="center")
    )
    style.addElement(
        TextProperties(
            fontsize="8pt",
            fontweight="normal",
            fontname="Source Sans Pro",
            fontfamily="Source Sans Pro",
            color=self.rgb_to_hex(self.colors["address"]),
            # texttransform="uppercase",
            fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("InfosStyle")
    style.addElement(
        ParagraphProperties(textalign="center", margintop="0cm", marginbottom="0.2cm", verticalalign="center")
    )
    style.addElement(
        TextProperties(
            fontsize="9pt",
            fontweight="normal",
            fontname="Calibri",
            fontfamily="Calibri",
            # fontname="Candara",
            # fontfamily="Candara",
            color=self.rgb_to_hex(self.colors["infos"]),
            # texttransform="uppercase",
            # fontvariant="small-caps",
        )
    )

    style = self.add_auto_style("LanguageStyle", "text")
    style.addElement(
        TextProperties(
            fontweight="bold", color=self.rgb_to_hex(self.colors["highlight"], lighten=0.1), textshadow="1pt 1pt"
        )
    )

    style = self.add_paragraph_style("TechsStyleBase")
    style.addElement(
        ParagraphProperties(
            textalign="center", margintop="0.15cm", marginbottom="0.15cm", verticalalign="center", lineheight="125%"
        )
    )
    style.addElement(
        TextProperties(
            fontsize="7pt",
            fontweight="bold",
            fontname="Roboto Condensed",
            fontfamily="Roboto Condensed",
            color=self.rgb_to_hex(self.colors["infos"]),
        )
    )

    style = self.add_auto_style("TechsStyle", "text")
    style.addElement(TextProperties(backgroundcolor="transparent"))

    props = TextProperties(backgroundcolor=self.rgb_to_hex(self.colors["highlight"], lighten=0.9))
    style.addElement(props)

    props.setAttrNS(loextns, "char-shading-value", "0")
    props.setAttrNS(loextns, "padding-left", "0.08cm")
    props.setAttrNS(loextns, "padding-right", "0.08cm")
    props.setAttrNS(loextns, "padding-top", "0.02cm")
    props.setAttrNS(loextns, "padding-bottom", "0.02cm")
    props.setAttrNS(loextns, "border", "1.0pt solid " + self.rgb_to_hex(self.colors["highlight"], lighten=0.5))
    props.setAttrNS(loextns, "shadow", "none")

    style = self.add_paragraph_style("LeftTitle")
    style.addElement(
        ParagraphProperties(
            textalign="right", margintop="0cm", marginbottom="0.cm", marginright="0.3cm", verticalalign="center"
        )
    )
    style.addElement(
        TextProperties(
            fontsize="11pt",
            fontweight="bold",
            fontname="Verdana",
            fontfamily="Verdana",
            # fontweight="normal",
            # fontname="Calibri",
            # fontfamily="Calibri",
            color=self.rgb_to_hex(self.colors["highlight"]),
            fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("ApplyingPositionStyle")
    style.addElement(
        ParagraphProperties(
            textalign="center", margintop="0cm", marginbottom="0.0cm", marginleft="0cm", verticalalign="center"
        )
    )
    style.addElement(
        TextProperties(
            fontsize="11pt",
            fontweight="normal",
            fontname="Calibri",
            fontfamily="Calibri",
            color=self.rgb_to_hex(self.colors["text"]),
            fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("SkillLineParagraphStyle")
    style.addElement(
        ParagraphProperties(
            textalign="left",
            margintop="0cm",
            marginbottom="0.0cm",
            marginleft="0.0cm",
            verticalalign="center",
            lineheight="100%",
        )
    )
    style.addElement(
        TextProperties(
            fontsize="6pt",
            fontweight="normal",
            fontname="Liberation Serif",
            fontfamily="Liberation Serif",
            color=self.rgb_to_hex(self.colors["text"]),
            # textshadow="4pt 4pt",
            # fontvariant="small-caps",
        )
    )

    style = self.add_paragraph_style("MainText")
    style.addElement(
        ParagraphProperties(
            textalign="left",
            margintop="0cm",
            marginbottom="0.0cm",
            marginleft="0.2cm",
            verticalalign="center",
            lineheight="120%",
        )
    )
    style.addElement(
        TextProperties(
            fontsize=self.text_size,
            fontweight="normal",
            fontname="Source Sans Pro",
            fontfamily="Source Sans Pro",
            color=self.rgb_to_hex(self.colors["text"]),
            textshadow="4pt 4pt",
            # fontvariant="small-caps",
        )
    )

    # usable page width in centimeters:
    pwidth = self.page_width

    style = self.add_auto_table_style("MainTableStyle")
    style.addElement(TableProperties(width=f"{pwidth}cm", marginleft="-1.0cm", align="left"))

    style = self.add_auto_style("MainTableRow", "table-row")
    style.addElement(TableRowProperties(keeptogether="always"))

    left_size = pwidth * self.left_col_ratio
    right_size = pwidth - left_size
    style = self.add_auto_table_column_style("MainTableCol0Style")
    style.addElement(TableColumnProperties(columnwidth=f"{left_size:.2f}cm"))  # , relcolumnwidth=f"{rel1}*"
    style = self.add_auto_table_column_style("MainTableCol1Style")
    style.addElement(TableColumnProperties(columnwidth=f"{right_size:.2f}cm"))  # , relcolumnwidth=f"{rel2}*"

    style = self.add_auto_table_cell_style("DefaultCellStyle")
    style.addElement(TableCellProperties(padding="0cm", border="none"))
    style = self.add_auto_table_cell_style("VCenteredCellStyle")
    style.addElement(TableCellProperties(padding="0cm", border="none", verticalalign="middle"))

    style = self.add_auto_table_cell_style("JobCellStyle")
    style.addElement(TableCellProperties(padding="0cm", border="none", verticalalign="middle"))

    style = self.add_auto_style("MainTableWithBreakStyle", "table", parentstylename="MainTableStyle")
    style.addElement(TableProperties(breakbefore="page", width=f"{pwidth}cm", marginleft="-1.0cm", align="left"))

    settings = self.desc["settings"]
    nsteps = settings["num_skill_steps"]
    pad = settings["skill_step_padding"]
    scol = settings["skill_start_color"]
    ecol = settings["skill_end_color"]
    mcol = settings["skill_missing_color"]
    swidth = settings["skill_stroke_width"]

    style = self.add_paragraph_style("SkillElemStyle")
    style.addElement(
        ParagraphProperties(
            textalign="left",
            marginleft=f"{pad}cm",
            margintop="0.05cm",
            marginbottom="0.05cm",
            verticalalign="center",
        )
    )
    style.addElement(
        TextProperties(
            fontsize="7pt",
            fontweight="bold",
            fontname="Source Sans Pro",
            fontfamily="Source Sans Pro",
            color=self.rgb_to_hex(self.colors["darktext"]),
            # texttransform="uppercase",
            # fontvariant="small-caps",
        )
    )

    # Default gray line style:
    style = self.add_auto_graphic_style("SkillLineStyleDef")
    style.addElement(
        GraphicProperties(
            wrap="none",
            runthrough="background",
            strokewidth=f"{swidth}cm",
            flowwithtext="false",
            # allowoverlap="true",
            markerstartwidth="0.0cm",
            markerendwidth="0.0cm",
            strokecolor=self.rgb_to_hex(mcol),
            paddingtop="0.0cm",
            paddingbottom="0.0cm",
            paddingleft="0.0cm",
            paddingright="0.0cm",
            wrapinfluenceonposition="once-concurrent",
            verticalpos="paragraph",
            verticalrel="from-top",
            horizontalpos="from-left",
            horizontalrel="paragraph",
        )
    )

    # Add the line element styles:
    for i in range(nsteps):
        x = i / (nsteps - 1)
        col = (
            int(scol[0] * (1.0 - x) + ecol[0] * x),
            int(scol[1] * (1.0 - x) + ecol[1] * x),
            int(scol[2] * (1.0 - x) + ecol[2] * x),
        )

        style = self.add_auto_graphic_style(f"SkillLineStyle{i}")
        style.addElement(
            GraphicProperties(
                wrap="none",
                runthrough="background",
                strokewidth=f"{swidth}cm",
                flowwithtext="false",
                # allowoverlap="true",
                markerstartwidth="0.0cm",
                markerendwidth="0.0cm",
                strokecolor=self.rgb_to_hex(col),
                paddingtop="0.0cm",
                paddingbottom="0.0cm",
                paddingleft="0.0cm",
                paddingright="0.0cm",
                wrapinfluenceonposition="once-concurrent",
                verticalpos="paragraph",
                verticalrel="from-top",
                horizontalpos="from-left",
                horizontalrel="paragraph",
            )
        )

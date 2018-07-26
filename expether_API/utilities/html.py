import os
import config.www.style.html_table as tbl
import config.www.style.html_caption as caption
from jinja2 import (
    Environment,
    PackageLoader,
    select_autoescape
)

'''
Class to generate and modify HTML files
'''


class html(object):
    @staticmethod
    def generate_table(docs, header, name):
        html = (
            "<!DOCTYPE html>"
            "<html>"
            "<head>"
            "<title>Title</title>"
            '<meta charset="UTF-8">'
            "<style>"
            "table {"
        )
        for conf_name, conf_val in tbl.table_style.items():
            html += "%s: %s;" % (conf_name, conf_val)
        html += (
            "}"
            "th {"
        )
        for conf_name, conf_val in tbl.table_style_header.items():
            html += "%s: %s;" % (conf_name, conf_val)
        html += (
            "}"
            "td {"
        )
        for conf_name, conf_val in tbl.table_style_body.items():
            html += "%s: %s;" % (conf_name, conf_val)
        html += (
            "}"
            "tr:nth-child(even) {background-color: %s"
        ) % (tbl.table_row_separator["background-color"])

        html += (
            "}"
            "caption {"
        )
        for conf_name, conf_val in caption.caption_style.items():
            html += "%s: %s;" % (conf_name, conf_val)

        html += (
            "}"
            "</style>"
            "</head>"
            "<body>"
            "<h2>EEM</h2>"
            "<table>"
            "<caption>%s</caption<"
            "<tr>"
        ) % (name)

        for head in header:
            html += "<th>%s</th>" % (head)
        html += "</tr>"

        for doc in docs:
            for x in range(0, len(header)):
                html += (
                    "<td>%s</td>"
                ) % (doc[header[x]])
            html += "</tr>"
        html += (
            "</body>"
            "</html>"
        )

        return html

    @staticmethod
    def generate_table_jinja(docs):
        env = Environment(
            loader=PackageLoader('config.www', 'templates'),
            autoescape=select_autoescape(['html'])
        )

        template = env.get_template('table.html')
        return template.render(
                tbl_style=tbl.table_style,
                tbl_header=tbl.table_style_header,
                tbl_body=tbl.table_style_body,
                background=tbl.table_row_separator["background-color"],
                caption=caption.caption_style,
                docs=docs
        )

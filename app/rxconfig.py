import reflex as rx
import reflex_xy as rxy
from reflex_base.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="xy_compare",
    plugins=[
        rxy.XYPlugin(),
        SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(),
    ],
)

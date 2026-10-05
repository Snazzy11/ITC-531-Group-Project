"""Draws architecture-diagram.png.

    uv run --with matplotlib python milestones/milestone4/diagram.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK = "#1f2937"
MUTED = "#6b7280"
API_PATH = "#2563eb"
PRESIGNED = "#d97706"
BACKGROUND = "#5b6575"

BOXES = {
    "client": (1.6, 6.0, "Client", "browser or curl"),
    "gateway": (5.2, 6.0, "Gateway", "nginx, :8000"),
    "app": (8.8, 6.0, "FastAPI app", "app/files.py, app/api.py\nports/storage.py"),
    "db": (13.0, 7.6, "Postgres", "files, images, items"),
    "broker": (13.0, 4.9, "RabbitMQ", "jobs.image_processor"),
    "worker": (13.0, 2.2, "Image worker", "file -k, re-encode"),
    "store": (6.4, 1.6, "Object store (S3 API)", "private bucket; RustFS locally, :9000"),
}
WIDE = {"store": 4.4}


def box(ax, name):
    x, y, title, subtitle = BOXES[name]
    width, height = WIDE.get(name, 2.6), 1.25
    ax.add_patch(
        FancyBboxPatch(
            (x - width / 2, y - height / 2),
            width,
            height,
            boxstyle="round,pad=0.02,rounding_size=0.15",
            facecolor="white",
            edgecolor=INK,
            linewidth=1.4,
        )
    )
    ax.text(x, y + 0.22, title, ha="center", va="center", fontsize=12, weight="bold", color=INK)
    ax.text(x, y - 0.25, subtitle, ha="center", va="center", fontsize=8.5, color=MUTED)


def arrow(ax, start, end, color, label, style="-", rad=0.0, both=False, offset=(0, 0), width=1.6):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="<|-|>" if both else "-|>",
            mutation_scale=14,
            color=color,
            linewidth=width,
            linestyle=style,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=4,
            shrinkB=4,
        )
    )
    mx, my = (start[0] + end[0]) / 2 + offset[0], (start[1] + end[1]) / 2 + offset[1]
    ax.text(
        mx, my, label, ha="center", va="center", fontsize=8.5, color=color,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5},
    )


fig, ax = plt.subplots(figsize=(15, 9.2))
ax.set_xlim(0, 15)
ax.set_ylim(0, 9.2)
ax.axis("off")

ax.text(0.2, 8.95, "Campus Seekr: storage architecture (Milestone 4)", fontsize=15, weight="bold", color=INK, va="top")
ax.text(
    0.2, 8.5,
    "The bucket is private. A client reaches stored bytes only through the API (blue) or a presigned URL (orange).",
    fontsize=10, color=MUTED, va="top",
)

for name in BOXES:
    box(ax, name)

# Through the API: JSON everywhere, and /files bytes, checked before any write.
arrow(ax, (2.9, 6.15), (3.9, 6.15), API_PATH, "", both=True)
ax.text(3.4, 6.75, "JSON, and /files\nuploads + downloads", ha="center", fontsize=8.5, color=API_PATH)
arrow(ax, (6.5, 6.0), (7.5, 6.0), API_PATH, "", both=True)
arrow(ax, (10.1, 6.4), (11.7, 7.5), API_PATH, "index rows", offset=(-0.15, 0.25))
arrow(ax, (8.8, 5.37), (7.6, 2.23), API_PATH, "/files bytes, after\nthe 413/400 checks", both=True, offset=(0.75, 0.1))
ax.text(
    5.2, 4.6,
    "upload_url and photo_url are\nsigned inside the app (no call\nto the store) and returned as JSON",
    ha="center", fontsize=8.5, color=API_PATH, style="italic",
)

# Background work.
arrow(ax, (10.1, 5.6), (11.7, 5.0), BACKGROUND, "")
ax.text(10.9, 4.85, "job after\n/complete", ha="center", va="top", fontsize=8.5, color=BACKGROUND)
arrow(ax, (13.0, 4.27), (13.0, 2.83), BACKGROUND, "", width=1.3)
arrow(ax, (11.7, 2.0), (8.6, 1.6), BACKGROUND, "reads uploads/pending/,\nwrites items/.../photo.jpg", both=True, offset=(0.2, 0.45))
arrow(ax, (14.3, 2.5), (14.3, 7.3), BACKGROUND, "ready /\nrejected", rad=0.35, offset=(0.85, 0))

# The presigned path: bytes go directly between the client and the store.
arrow(ax, (1.3, 5.37), (4.2, 1.95), PRESIGNED, "", style="--", width=2.6)
arrow(ax, (4.2, 1.25), (0.9, 5.37), PRESIGNED, "", style="--", width=2.6)
ax.text(0.95, 3.1, "presigned GET\nphoto_url: the photo\ncomes from the store", ha="center", fontsize=9, color=PRESIGNED, weight="bold")
ax.text(4.1, 3.55, "presigned PUT\nupload_url: the photo\ngoes to the store", ha="center", fontsize=9, color=PRESIGNED, weight="bold")
ax.text(
    2.6, 0.55, "Photo bytes never pass through the gateway or the API.",
    ha="center", fontsize=9, color=PRESIGNED, style="italic",
)

ax.legend(
    handles=[
        Line2D([], [], color=API_PATH, linewidth=2, label="through the API"),
        Line2D([], [], color=PRESIGNED, linewidth=2.6, linestyle="--", label="presigned: client <-> store directly"),
        Line2D([], [], color=BACKGROUND, linewidth=2, label="background processing"),
    ],
    loc="lower right", frameon=False, fontsize=9,
)

fig.savefig(Path(__file__).with_name("architecture-diagram.png"), dpi=150, bbox_inches="tight")

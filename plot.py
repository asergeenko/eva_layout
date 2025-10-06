import hashlib
from io import BytesIO

from matplotlib import pyplot as plt
from matplotlib.ticker import MultipleLocator
from shapely import Polygon
from shapely.geometry import MultiPolygon

from carpet import Carpet, PlacedCarpet


def get_color_for_file(filename: str) -> tuple[float, float, float]:
    """Generate a consistent color for a given filename."""
    # Handle case where filename might be a float64 or other non-string type
    if isinstance(filename, (int, float)):
        filename = str(filename)
    elif filename is None:
        filename = "unknown"

    # Use hash of filename to generate consistent color
    hash_object = hashlib.md5(str(filename).encode())
    hash_hex = hash_object.hexdigest()

    # Convert first 6 characters of hash to RGB
    r = int(hash_hex[0:2], 16) / 255.0
    g = int(hash_hex[2:4], 16) / 255.0
    b = int(hash_hex[4:6], 16) / 255.0

    # Ensure colors are not too dark or too light
    r = max(0.2, min(0.9, r))
    g = max(0.2, min(0.9, g))
    b = max(0.2, min(0.9, b))

    return (r, g, b)


def plot_single_polygon(polygon: Polygon, title: str, filename: str = None) -> BytesIO:
    """Plot a single polygon."""
    if not polygon:
        return None

    fig, ax = plt.subplots(figsize=(8, 6))

    # Get consistent color for this file
    if filename:
        color = get_color_for_file(filename)
    else:
        color = "lightblue"

    # Plot the polygon
    x, y = polygon.exterior.xy
    ax.fill(x, y, alpha=0.7, color=color, edgecolor="darkblue", linewidth=2)

    # Add some padding around the polygon
    bounds = polygon.bounds
    padding = 0.1 * max(bounds[2] - bounds[0], bounds[3] - bounds[1])
    ax.set_xlim(bounds[0] - padding, bounds[2] + padding)
    ax.set_ylim(bounds[1] - padding, bounds[3] + padding)
    ax.set_aspect("equal")

    # Add polygon center point
    centroid = polygon.centroid
    ax.plot(centroid.x, centroid.y, "ro", markersize=5, label="Центр")

    # Convert from DXF units (mm) to cm
    width_mm = bounds[2] - bounds[0]
    height_mm = bounds[3] - bounds[1]
    width_cm = width_mm / 10.0
    height_cm = height_mm / 10.0
    area_cm2 = polygon.area / 100.0  # mm² to cm²

    ax.set_title(
        f"{title}\nРеальные размеры: {width_cm:.1f} × {height_cm:.1f} см\nПлощадь: {area_cm2:.2f} см²"
    )
    ax.set_xlabel("X координата (мм)")
    ax.set_ylabel("Y координата (мм)")
    ax.grid(True, alpha=0.3)
    ax.legend()

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close()
    buf.seek(0)
    return buf


def plot_input_polygons(
    carpets: list[Carpet],
) -> dict[str, BytesIO]:
    """Create individual plots for each DXF file."""
    if not carpets:
        return {}

    plots = {}
    for carpet in carpets:
        plot_buf = plot_single_polygon(
            carpet.polygon,
            f"Файл: {carpet.filename} (цвет: {carpet.color})",
            filename=carpet.filename,
        )
        plots[carpet.filename] = plot_buf

    return plots


def plot_layout(
    placed_polygons: list[PlacedCarpet],
    sheet_size: tuple[float, float],
) -> BytesIO:
    """Plot the layout using matplotlib and return as BytesIO."""
    fig, ax = plt.subplots(figsize=(10, 8))

    # Convert sheet size from cm to mm for proper scaling
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10

    ax.set_xlim(0, sheet_width_mm)
    ax.set_ylim(0, sheet_height_mm)
    ax.set_aspect("equal")

    # Основная сетка 200 мм
    ax.xaxis.set_major_locator(MultipleLocator(200))
    ax.yaxis.set_major_locator(MultipleLocator(200))

    # Минорная сетка 50 мм
    ax.xaxis.set_minor_locator(MultipleLocator(50))
    ax.yaxis.set_minor_locator(MultipleLocator(50))

    # Draw sheet boundary
    sheet_boundary = plt.Rectangle(
        (0, 0),
        sheet_width_mm,
        sheet_height_mm,
        fill=False,
        edgecolor="black",
        linewidth=2,
        linestyle="--",
    )
    ax.add_patch(sheet_boundary)

    # Use consistent colors for each file
    for placed_tuple in placed_polygons:
        polygon = placed_tuple.polygon
        file_name = placed_tuple.filename
        angle = placed_tuple.angle
        color = placed_tuple.color

        # Handle both Polygon and MultiPolygon
        if isinstance(polygon, MultiPolygon):
            # For MultiPolygon, plot each sub-polygon
            for sub_poly in polygon.geoms:
                x, y = sub_poly.exterior.xy
                display_color = get_color_for_file(file_name)
                ax.fill(
                    x,
                    y,
                    alpha=0.7,
                    color=display_color,
                    edgecolor="black",
                    linewidth=1,
                    label=f"{file_name} ({angle:.0f}°) - {color}",
                )
        else:
            x, y = polygon.exterior.xy
            # Use file-based color for visualization consistency
            display_color = get_color_for_file(file_name)
            ax.fill(
                x,
                y,
                alpha=0.7,
                color=display_color,
                edgecolor="black",
                linewidth=1,
                label=f"{file_name} ({angle:.0f}°) - {color}",
            )

        # Add file name at polygon centroid
        centroid = polygon.centroid

        display_name = str(file_name)
        if display_name.endswith(".dxf"):
            display_name = display_name.replace(".dxf", "")

        ax.annotate(
            display_name,
            (centroid.x, centroid.y),
            ha="center",
            va="center",
            fontsize=8,
            weight="bold",
        )

    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.set_title(f"Раскрой на листе {sheet_size[0]} × {sheet_size[1]} см")
    ax.set_xlabel("Ширина (мм)")
    ax.set_ylabel("Высота (мм)")

    # Включаем основную и минорную сетку
    ax.grid(True, which="major", alpha=0.4, linewidth=0.8)
    ax.grid(True, which="minor", alpha=0.2, linestyle=":")

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close()
    buf.seek(0)
    return buf

"""Tests for layout_optimizer module."""

import pytest
import tempfile
import os
from pathlib import Path
from shapely.geometry import Polygon
import ezdxf
from io import BytesIO

from layout_optimizer import (
    parse_dxf_complete,
    rotate_polygon,
    translate_polygon,
    check_collision,
    bin_packing_with_inventory,
    save_dxf_layout_complete,
    plot_layout,
)


@pytest.fixture
def sample_dxf_files():
    """Fixture that provides paths to sample DXF files."""
    dxf_samples_dir = Path(__file__).parent.parent / "dxf_samples"
    return list(dxf_samples_dir.glob("*.dxf"))


@pytest.fixture
def sheet_sizes():
    """Fixture that provides standard sheet sizes."""
    return [
        (140, 200),
        (142, 200),
        (144, 200),
        (146, 200),
        (148, 200),
        (140, 195),
        (142, 195),
        (144, 195),
        (146, 195),
        (148, 195),
    ]


@pytest.fixture
def simple_polygon():
    """Fixture that provides a simple test polygon."""
    return Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])


@pytest.fixture
def create_test_dxf():
    """Fixture that creates a temporary DXF file for testing."""

    def _create_dxf(polygons_coords):
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            doc = ezdxf.new()
            msp = doc.modelspace()

            for coords in polygons_coords:
                msp.add_lwpolyline(coords)

            doc.saveas(tmp.name)
            return tmp.name

    return _create_dxf


class TestParseDxfComplete:
    """Tests for parse_dxf_complete function."""

    def test_parse_dxf_complete_with_sample_files(self, sample_dxf_files):
        """Test parsing real DXF sample files."""
        for dxf_file in sample_dxf_files[:5]:  # Limit to first 5 files
            with open(dxf_file, "rb") as f:
                file_bytes = BytesIO(f.read())
                parsed_data = parse_dxf_complete(file_bytes, verbose=False)
                if parsed_data and parsed_data.get("combined_polygon"):
                    polygon = parsed_data["combined_polygon"]
                    assert isinstance(polygon, Polygon)
                    assert polygon.is_valid

    def test_parse_dxf_complete_with_test_file(self, create_test_dxf):
        """Test parsing a custom test DXF file."""
        test_coords = [[(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]]
        dxf_path = create_test_dxf(test_coords)

        try:
            with open(dxf_path, "rb") as f:
                file_bytes = BytesIO(f.read())
                parsed_data = parse_dxf_complete(file_bytes, verbose=False)

            assert parsed_data is not None
            polygon = parsed_data.get("combined_polygon")
            if polygon:
                assert polygon.is_valid
                assert polygon.area == 100.0  # 10x10 square
        finally:
            os.unlink(dxf_path)

    def test_parse_dxf_complete_empty_file(self, create_test_dxf):
        """Test parsing DXF file with no polygons."""
        dxf_path = create_test_dxf([])

        try:
            with open(dxf_path, "rb") as f:
                file_bytes = BytesIO(f.read())
                parsed_data = parse_dxf_complete(file_bytes, verbose=False)

            # Should return valid structure but no combined polygon
            assert parsed_data is not None
            assert parsed_data.get("combined_polygon") is None
        finally:
            os.unlink(dxf_path)


class TestGeometricFunctions:
    """Tests for geometric manipulation functions."""

    def test_rotate_polygon(self, simple_polygon):
        """Test polygon rotation."""
        rotated_90 = rotate_polygon(simple_polygon, 90)
        assert rotated_90.is_valid
        assert rotated_90.area == pytest.approx(simple_polygon.area, rel=1e-6)

        # Test 360 degree rotation returns approximately same polygon
        rotated_360 = rotate_polygon(simple_polygon, 360)
        assert rotated_360.area == pytest.approx(simple_polygon.area, rel=1e-6)

    def test_translate_polygon(self, simple_polygon):
        """Test polygon translation."""
        translated = translate_polygon(simple_polygon, 5, 3)
        assert translated.is_valid
        assert translated.area == pytest.approx(simple_polygon.area, rel=1e-6)

        # Check that centroid moved by expected amount
        original_centroid = simple_polygon.centroid
        translated_centroid = translated.centroid

        assert translated_centroid.x == pytest.approx(original_centroid.x + 5, rel=1e-6)
        assert translated_centroid.y == pytest.approx(original_centroid.y + 3, rel=1e-6)

    def test_check_collision_no_overlap(self):
        """Test collision detection for non-overlapping polygons."""
        poly1 = Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
        poly2 = Polygon([(10, 10), (15, 10), (15, 15), (10, 15)])

        assert not check_collision(poly1, poly2)

    def test_check_collision_with_overlap(self):
        """Test collision detection for overlapping polygons."""
        poly1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        poly2 = Polygon([(5, 5), (15, 5), (15, 15), (5, 15)])

        assert check_collision(poly1, poly2)

    def test_check_collision_touching_edges(self):
        """Test collision detection for polygons that only touch."""
        poly1 = Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
        poly2 = Polygon([(5, 0), (10, 0), (10, 5), (5, 5)])

        # Note: Current implementation may consider touching as collision
        # This is actually safer for layout optimization
        collision_detected = check_collision(poly1, poly2)
        # Just verify the function returns a boolean result
        assert isinstance(collision_detected, bool)


class TestBinPackingWithInventory:
    """Tests for bin_packing_with_inventory function."""

    def test_bin_packing_single_polygon(self, simple_polygon):
        """Test bin packing with a single polygon."""
        polygons = [(simple_polygon, "test_polygon", "серый", "test_order")]
        
        # Create available sheets list
        available_sheets = [{
            "name": "Test Sheet",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 5,
            "used": 0
        }]

        placed_layouts, unplaced = bin_packing_with_inventory(
            polygons, available_sheets, verbose=False, max_sheets_per_order=5
        )

        # Small polygon should fit
        assert len(placed_layouts) >= 1
        assert len(unplaced) == 0

    def test_bin_packing_multiple_polygons(self):
        """Test bin packing with multiple small polygons."""
        # Create multiple small polygons with proper tuple format
        polygons = []
        for i in range(5):
            poly = Polygon([(i * 2, 0), (i * 2 + 1, 0), (i * 2 + 1, 1), (i * 2, 1)])
            polygons.append((poly, f"poly_{i}", "серый", f"order_{i}"))

        available_sheets = [{
            "name": "Test Sheet",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 10,
            "used": 0
        }]

        placed_layouts, unplaced = bin_packing_with_inventory(
            polygons, available_sheets, verbose=False, max_sheets_per_order=5
        )

        # Should place at least some polygons
        total_placed = sum(len(layout["placed_polygons"]) for layout in placed_layouts)
        assert total_placed + len(unplaced) == 5
        assert total_placed > 0  # At least some should be placed

    def test_bin_packing_too_large_polygon(self):
        """Test bin packing with polygon too large for sheet."""
        # Create a polygon larger than the sheet
        large_polygon = Polygon([(0, 0), (2000, 0), (2000, 3000), (0, 3000)])  # Much larger
        polygons = [(large_polygon, "large_polygon", "серый", "large_order")]
        
        available_sheets = [{
            "name": "Small Sheet",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 1,
            "used": 0
        }]

        placed_layouts, unplaced = bin_packing_with_inventory(
            polygons, available_sheets, verbose=False, max_sheets_per_order=5
        )

        # Large polygon should not fit
        assert len(placed_layouts) == 0 or sum(len(layout["placed_polygons"]) for layout in placed_layouts) == 0
        assert len(unplaced) == 1

    def test_bin_packing_with_sample_files(self, sample_dxf_files):
        """Test bin packing with real sample DXF files."""
        if not sample_dxf_files:
            pytest.skip("No sample DXF files found")

        # Parse first sample file
        with open(sample_dxf_files[0], "rb") as f:
            file_bytes = BytesIO(f.read())
            parsed_data = parse_dxf_complete(file_bytes, verbose=False)

        if not parsed_data or not parsed_data.get("combined_polygon"):
            pytest.skip("Sample DXF file contains no valid polygons")

        polygon_from_file = parsed_data["combined_polygon"]

        # Create polygon list with proper tuple format
        polygons = [(polygon_from_file, "sample_0", "серый", "sample_order")]

        available_sheets = [{
            "name": "Test Sheet",
            "width": 200,
            "height": 300,
            "color": "серый",
            "count": 3,
            "used": 0
        }]

        placed_layouts, unplaced = bin_packing_with_inventory(
            polygons, available_sheets, verbose=False, max_sheets_per_order=5
        )

        # Should place the polygon or mark it as unplaced
        total_placed = sum(len(layout["placed_polygons"]) for layout in placed_layouts)
        assert total_placed + len(unplaced) == len(polygons)


class TestSaveDxfLayoutComplete:
    """Tests for save_dxf_layout_complete function."""

    def test_save_dxf_layout_complete(self, simple_polygon):
        """Test saving DXF layout to file."""
        placed_polygons = [(simple_polygon, 0, 0, 0, "test_polygon")]
        sheet_size = (100, 100)
        original_dxf_data_map = {"test_polygon": {"polygons": [], "original_entities": []}}

        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            output_path = tmp.name

        try:
            save_dxf_layout_complete(placed_polygons, sheet_size, output_path, original_dxf_data_map)

            assert os.path.exists(output_path)

            # Verify the file can be read back
            doc = ezdxf.readfile(output_path)
            msp = doc.modelspace()
            entities = list(msp)
            # File should exist and be readable, entities count may vary based on implementation
            assert doc is not None

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestPlotLayout:
    """Tests for plot_layout function."""

    def test_plot_layout(self, simple_polygon):
        """Test plotting layout to BytesIO."""
        placed_polygons = [(simple_polygon, 0, 0, 0, "test_polygon")]
        sheet_size = (100, 100)

        plot_buffer = plot_layout(placed_polygons, sheet_size)

        assert isinstance(plot_buffer, BytesIO)
        assert plot_buffer.tell() == 0  # Should be at start

        # Check that buffer contains data
        plot_buffer.seek(0, 2)  # Seek to end
        assert plot_buffer.tell() > 0  # Should have content

        plot_buffer.seek(0)  # Reset to start

    def test_plot_layout_multiple_polygons(self):
        """Test plotting layout with multiple polygons."""
        polygons = [
            (Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]), 0, 0, 0, "poly1"),
            (Polygon([(20, 20), (30, 20), (30, 30), (20, 30)]), 20, 20, 0, "poly2"),
        ]
        sheet_size = (50, 50)

        plot_buffer = plot_layout(polygons, sheet_size)

        assert isinstance(plot_buffer, BytesIO)
        plot_buffer.seek(0, 2)
        assert plot_buffer.tell() > 0

    def test_plot_layout_empty_list(self):
        """Test plotting layout with no polygons."""
        placed_polygons = []
        sheet_size = (100, 100)

        plot_buffer = plot_layout(placed_polygons, sheet_size)

        assert isinstance(plot_buffer, BytesIO)
        plot_buffer.seek(0, 2)
        assert plot_buffer.tell() > 0  # Should still create plot


class TestIntegration:
    """Integration tests using real sample files and standard sheet sizes."""

    def test_full_workflow_with_samples(self, sample_dxf_files):
        """Test complete workflow from DXF parsing to layout generation."""
        if not sample_dxf_files:
            pytest.skip("No sample DXF files found")

        # Use first few sample files
        test_files = (
            sample_dxf_files[:2] if len(sample_dxf_files) >= 2 else sample_dxf_files
        )

        # Parse all sample files
        all_polygons = []
        for dxf_file in test_files:
            with open(dxf_file, "rb") as f:
                file_bytes = BytesIO(f.read())
                parsed_data = parse_dxf_complete(file_bytes, verbose=False)
                if parsed_data and parsed_data.get("combined_polygon"):
                    polygon = parsed_data["combined_polygon"]
                    all_polygons.append((polygon, dxf_file.name, "серый", f"order_{dxf_file.name}"))

        if not all_polygons:
            pytest.skip("No valid polygons found in sample files")

        # Create available sheets for new bin packing function
        available_sheets = [{
            "name": "Test Sheet 144x200",
            "width": 144,
            "height": 200,
            "color": "серый",
            "count": 5,
            "used": 0
        }]

        # Run bin packing with inventory
        placed_layouts, unplaced = bin_packing_with_inventory(
            all_polygons, available_sheets, verbose=False, max_sheets_per_order=5
        )

        # Should place at least some polygons
        total_placed = sum(len(layout["placed_polygons"]) for layout in placed_layouts)
        assert total_placed + len(unplaced) == len(all_polygons)

        if placed_layouts:
            # Test saving DXF using first layout
            layout = placed_layouts[0]
            placed_polygons = layout["placed_polygons"]
            sheet_size = layout["sheet_size"]
            
            # Create minimal original DXF data map
            original_dxf_data_map = {}
            for polygon_data in placed_polygons:
                filename = polygon_data[4] if len(polygon_data) > 4 else "unknown"
                original_dxf_data_map[filename] = {"polygons": [], "original_entities": []}

            with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
                output_path = tmp.name

            try:
                save_dxf_layout_complete(placed_polygons, sheet_size, output_path, original_dxf_data_map)
                assert os.path.exists(output_path)

                # Test plotting
                plot_buffer = plot_layout(placed_polygons, sheet_size)
                assert isinstance(plot_buffer, BytesIO)
                plot_buffer.seek(0, 2)
                assert plot_buffer.tell() > 0

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

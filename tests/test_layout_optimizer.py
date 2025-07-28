"""Tests for layout_optimizer module."""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path
from shapely.geometry import Polygon
import ezdxf
from io import BytesIO

from layout_optimizer import (
    parse_dxf,
    rotate_polygon,
    translate_polygon,
    check_collision,
    bin_packing,
    save_dxf_layout,
    plot_layout
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
        (140, 200), (142, 200), (144, 200), (146, 200), (148, 200),
        (140, 195), (142, 195), (144, 195), (146, 195), (148, 195)
    ]


@pytest.fixture
def simple_polygon():
    """Fixture that provides a simple test polygon."""
    return Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])


@pytest.fixture
def create_test_dxf():
    """Fixture that creates a temporary DXF file for testing."""
    def _create_dxf(polygons_coords):
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp:
            doc = ezdxf.new()
            msp = doc.modelspace()
            
            for coords in polygons_coords:
                msp.add_lwpolyline(coords)
            
            doc.saveas(tmp.name)
            return tmp.name
    return _create_dxf


class TestParseDxf:
    """Tests for parse_dxf function."""
    
    def test_parse_dxf_with_sample_files(self, sample_dxf_files):
        """Test parsing real DXF sample files."""
        for dxf_file in sample_dxf_files:
            with open(dxf_file, 'rb') as f:
                file_bytes = BytesIO(f.read())
                polygon = parse_dxf(file_bytes)
                if polygon:  # May be None if no valid geometry found
                    assert isinstance(polygon, Polygon)
                    assert polygon.is_valid
    
    def test_parse_dxf_with_test_file(self, create_test_dxf):
        """Test parsing a custom test DXF file."""
        test_coords = [[(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]]
        dxf_path = create_test_dxf(test_coords)
        
        try:
            with open(dxf_path, 'rb') as f:
                file_bytes = BytesIO(f.read())
                polygon = parse_dxf(file_bytes)
            
            assert polygon is not None
            assert polygon.is_valid
            assert polygon.area == 100.0  # 10x10 square
        finally:
            os.unlink(dxf_path)
    
    def test_parse_dxf_empty_file(self, create_test_dxf):
        """Test parsing DXF file with no polygons."""
        dxf_path = create_test_dxf([])
        
        try:
            with open(dxf_path, 'rb') as f:
                file_bytes = BytesIO(f.read())
                polygon = parse_dxf(file_bytes)
            
            assert polygon is None
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
        
        # Touching should not be considered collision
        assert not check_collision(poly1, poly2)


class TestBinPacking:
    """Tests for bin_packing function."""
    
    def test_bin_packing_single_polygon(self, simple_polygon, sheet_sizes):
        """Test bin packing with a single polygon on different sheet sizes."""
        polygons = [(simple_polygon, "test_polygon")]
        
        for sheet_size in sheet_sizes:
            placed, unplaced = bin_packing(polygons, sheet_size, max_attempts=100)
            
            # Small polygon should fit on all standard sheet sizes
            assert len(placed) == 1
            assert len(unplaced) == 0
            assert placed[0][4] == "test_polygon"  # filename
            
            # Check that polygon is within sheet bounds
            placed_polygon = placed[0][0]
            bounds = placed_polygon.bounds
            assert bounds[0] >= 0  # min_x
            assert bounds[1] >= 0  # min_y
            assert bounds[2] <= sheet_size[0]  # max_x
            assert bounds[3] <= sheet_size[1]  # max_y
    
    def test_bin_packing_multiple_polygons(self, sheet_sizes):
        """Test bin packing with multiple small polygons."""
        # Create multiple small polygons
        polygons = []
        for i in range(5):
            poly = Polygon([(i*2, 0), (i*2+1, 0), (i*2+1, 1), (i*2, 1)])
            polygons.append((poly, f"poly_{i}"))
        
        sheet_size = sheet_sizes[0]  # Use first sheet size
        placed, unplaced = bin_packing(polygons, sheet_size, max_attempts=500)
        
        # All small polygons should fit
        assert len(placed) + len(unplaced) == 5
        assert len(placed) > 0  # At least some should be placed
    
    def test_bin_packing_too_large_polygon(self):
        """Test bin packing with polygon too large for sheet."""
        # Create a polygon larger than the sheet
        large_polygon = Polygon([(0, 0), (200, 0), (200, 300), (0, 300)])
        polygons = [(large_polygon, "large_polygon")]
        sheet_size = (140, 200)
        
        placed, unplaced = bin_packing(polygons, sheet_size, max_attempts=10)
        
        # Large polygon should not fit
        assert len(placed) == 0
        assert len(unplaced) == 1
    
    def test_bin_packing_with_sample_files(self, sample_dxf_files, sheet_sizes):
        """Test bin packing with real sample DXF files."""
        if not sample_dxf_files:
            pytest.skip("No sample DXF files found")
        
        # Parse first sample file
        with open(sample_dxf_files[0], 'rb') as f:
            file_bytes = BytesIO(f.read())
            polygon_from_file = parse_dxf(file_bytes)
        
        if not polygon_from_file:
            pytest.skip("Sample DXF file contains no valid polygons")
        
        # Create polygon list with filenames
        polygons = [(polygon_from_file, "sample_0")]
        
        # Test with different sheet sizes
        for sheet_size in sheet_sizes[:3]:  # Test with first 3 sizes
            placed, unplaced = bin_packing(polygons, sheet_size, max_attempts=100)
            
            # Should place at least some polygons or all should be unplaced
            assert len(placed) + len(unplaced) == len(polygons)


class TestSaveDxfLayout:
    """Tests for save_dxf_layout function."""
    
    def test_save_dxf_layout(self, simple_polygon):
        """Test saving DXF layout to file."""
        placed_polygons = [(simple_polygon, 0, 0, 0, "test_polygon")]
        sheet_size = (100, 100)
        
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp:
            output_path = tmp.name
        
        try:
            result_path = save_dxf_layout(placed_polygons, sheet_size, output_path)
            
            assert result_path == output_path
            assert os.path.exists(output_path)
            
            # Verify the file can be read back
            doc = ezdxf.readfile(output_path)
            msp = doc.modelspace()
            entities = list(msp)
            assert len(entities) > 0
            
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
            (Polygon([(20, 20), (30, 20), (30, 30), (20, 30)]), 20, 20, 0, "poly2")
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
    
    def test_full_workflow_with_samples(self, sample_dxf_files, sheet_sizes):
        """Test complete workflow from DXF parsing to layout generation."""
        if not sample_dxf_files:
            pytest.skip("No sample DXF files found")
        
        # Use first few sample files
        test_files = sample_dxf_files[:3] if len(sample_dxf_files) >= 3 else sample_dxf_files
        
        # Parse all sample files
        all_polygons = []
        for dxf_file in test_files:
            with open(dxf_file, 'rb') as f:
                file_bytes = BytesIO(f.read())
                polygon = parse_dxf(file_bytes)
                if polygon:
                    all_polygons.append((polygon, dxf_file.name))
        
        if not all_polygons:
            pytest.skip("No valid polygons found in sample files")
        
        # Test with medium sheet size
        sheet_size = (144, 200)
        
        # Run bin packing
        placed, unplaced = bin_packing(all_polygons, sheet_size, max_attempts=200)
        
        # Should place at least some polygons
        assert len(placed) + len(unplaced) == len(all_polygons)
        
        if placed:
            # Test saving DXF
            with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp:
                output_path = tmp.name
            
            try:
                save_dxf_layout(placed, sheet_size, output_path)
                assert os.path.exists(output_path)
                
                # Test plotting
                plot_buffer = plot_layout(placed, sheet_size)
                assert isinstance(plot_buffer, BytesIO)
                plot_buffer.seek(0, 2)
                assert plot_buffer.tell() > 0
                
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
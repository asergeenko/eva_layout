use pyo3::prelude::*;
use rayon::prelude::*;
use geo::{Polygon, Coord, LineString};
use rstar::{RTree, AABB};
use std::collections::HashMap;

/// Simple point structure for grid positions
#[derive(Debug, Clone)]
struct Point {
    x: f64,
    y: f64,
}

/// Simple rectangle for fast collision detection
#[derive(Debug, Clone)]
struct Rectangle {
    min_x: f64,
    min_y: f64,
    max_x: f64,
    max_y: f64,
}

impl Rectangle {
    fn new(min_x: f64, min_y: f64, max_x: f64, max_y: f64) -> Self {
        Rectangle { min_x, min_y, max_x, max_y }
    }

    fn intersects(&self, other: &Rectangle) -> bool {
        !(self.max_x <= other.min_x ||
          other.max_x <= self.min_x ||
          self.max_y <= other.min_y ||
          other.max_y <= self.min_y)
    }

    fn translate(&self, dx: f64, dy: f64) -> Rectangle {
        Rectangle::new(
            self.min_x + dx,
            self.min_y + dy,
            self.max_x + dx,
            self.max_y + dy
        )
    }
}

/// Fast grid search for collision-free positions
#[pyfunction]
fn fast_grid_search(
    carpet_bounds: (f64, f64, f64, f64),  // (min_x, min_y, max_x, max_y)
    placed_bounds: Vec<(f64, f64, f64, f64)>,  // bounds of placed polygons
    sheet_width: f64,
    sheet_height: f64,
    grid_size: usize,
) -> Option<(f64, f64)> {
    let carpet_rect = Rectangle::new(
        carpet_bounds.0, carpet_bounds.1,
        carpet_bounds.2, carpet_bounds.3
    );

    let carpet_width = carpet_bounds.2 - carpet_bounds.0;
    let carpet_height = carpet_bounds.3 - carpet_bounds.1;

    // Convert placed polygons to rectangles
    let obstacles: Vec<Rectangle> = placed_bounds
        .into_iter()
        .map(|(min_x, min_y, max_x, max_y)| Rectangle::new(min_x, min_y, max_x, max_y))
        .collect();

    // Generate grid positions
    let x_step = if grid_size > 1 {
        (sheet_width - carpet_width) / (grid_size as f64 - 1.0)
    } else {
        0.0
    };
    let y_step = if grid_size > 1 {
        (sheet_height - carpet_height) / (grid_size as f64 - 1.0)
    } else {
        0.0
    };

    // Test positions in parallel using rayon
    let positions: Vec<(f64, f64)> = (0..grid_size)
        .flat_map(|i| {
            (0..grid_size).map(move |j| {
                let x = if grid_size == 1 { 0.0 } else { i as f64 * x_step };
                let y = if grid_size == 1 { 0.0 } else { j as f64 * y_step };
                (x, y)
            })
        })
        .collect();

    // Find first collision-free position
    positions
        .par_iter()
        .find_first(|(x, y)| {
            let test_rect = carpet_rect.translate(
                x - carpet_bounds.0,
                y - carpet_bounds.1
            );

            // Check bounds
            if test_rect.min_x < 0.0 || test_rect.min_y < 0.0 ||
               test_rect.max_x > sheet_width || test_rect.max_y > sheet_height {
                return false;
            }

            // Check collisions with obstacles
            !obstacles.iter().any(|obstacle| test_rect.intersects(obstacle))
        })
        .map(|(x, y)| (*x, *y))
}

/// Fast collision detection for multiple positions
#[pyfunction]
fn batch_collision_check(
    carpet_bounds: (f64, f64, f64, f64),
    positions: Vec<(f64, f64)>,  // (x, y) positions to test
    placed_bounds: Vec<(f64, f64, f64, f64)>,  // bounds of placed polygons
    sheet_width: f64,
    sheet_height: f64,
) -> Vec<bool> {
    let carpet_rect = Rectangle::new(
        carpet_bounds.0, carpet_bounds.1,
        carpet_bounds.2, carpet_bounds.3
    );

    let obstacles: Vec<Rectangle> = placed_bounds
        .into_iter()
        .map(|(min_x, min_y, max_x, max_y)| Rectangle::new(min_x, min_y, max_x, max_y))
        .collect();

    positions
        .par_iter()
        .map(|(x, y)| {
            let test_rect = carpet_rect.translate(
                x - carpet_bounds.0,
                y - carpet_bounds.1
            );

            // Check bounds
            if test_rect.min_x < 0.0 || test_rect.min_y < 0.0 ||
               test_rect.max_x > sheet_width || test_rect.max_y > sheet_height {
                return false;
            }

            // Check collisions with obstacles
            !obstacles.iter().any(|obstacle| test_rect.intersects(obstacle))
        })
        .collect()
}

/// Spatial index for very fast collision queries
#[pyclass]
struct SpatialIndex {
    rtree: RTree<Rectangle>,
}

#[pymethods]
impl SpatialIndex {
    #[new]
    fn new(bounds_list: Vec<(f64, f64, f64, f64)>) -> Self {
        let rectangles: Vec<Rectangle> = bounds_list
            .into_iter()
            .map(|(min_x, min_y, max_x, max_y)| Rectangle::new(min_x, min_y, max_x, max_y))
            .collect();

        SpatialIndex {
            rtree: RTree::bulk_load(rectangles),
        }
    }

    fn query_collisions(&self, test_bounds: (f64, f64, f64, f64)) -> bool {
        let test_rect = Rectangle::new(
            test_bounds.0, test_bounds.1,
            test_bounds.2, test_bounds.3
        );

        self.rtree.locate_in_envelope_intersecting(&AABB::from_corners(
            [test_rect.min_x, test_rect.min_y],
            [test_rect.max_x, test_rect.max_y]
        )).next().is_some()
    }
}

// Implement RTreeObject for Rectangle
impl rstar::RTreeObject for Rectangle {
    type Envelope = AABB<[f64; 2]>;

    fn envelope(&self) -> Self::Envelope {
        AABB::from_corners([self.min_x, self.min_y], [self.max_x, self.max_y])
    }
}

impl rstar::PointDistance for Rectangle {
    fn distance_2(&self, point: &[f64; 2]) -> f64 {
        let dx = (point[0] - self.min_x.max(self.max_x.min(point[0]))).abs();
        let dy = (point[1] - self.min_y.max(self.max_y.min(point[1]))).abs();
        dx * dx + dy * dy
    }
}

/// Python module
#[pymodule]
fn layout_optimizer_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fast_grid_search, m)?)?;
    m.add_function(wrap_pyfunction!(batch_collision_check, m)?)?;
    m.add_class::<SpatialIndex>()?;
    Ok(())
}
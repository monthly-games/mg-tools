"""Tests for scripts/split_parts.py — refine_alpha_channel and helpers."""

import numpy as np
import pytest
from scripts.split_parts import (
    refine_alpha_channel,
    generate_trimap,
    remove_small_islands,
    guided_filter,
    count_mask_islands,
)


# ---------------------------------------------------------------------------
# refine_alpha_channel (primary target)
# ---------------------------------------------------------------------------
class TestRefineAlphaChannel:
    def test_output_shape_matches_input(self, small_mask, small_rgb_image):
        result = refine_alpha_channel(small_mask, small_rgb_image)
        assert result.shape == small_mask.shape

    def test_output_dtype_uint8(self, small_mask, small_rgb_image):
        result = refine_alpha_channel(small_mask, small_rgb_image)
        assert result.dtype == np.uint8

    def test_background_remains_zero(self, small_rgb_image):
        """All-zero mask → all-zero output."""
        mask = np.zeros((64, 64), dtype=np.uint8)
        result = refine_alpha_channel(mask, small_rgb_image)
        assert result.max() == 0

    def test_foreground_preserves_alpha(self, small_mask, small_rgb_image):
        """Non-zero mask region should produce non-zero alpha output."""
        result = refine_alpha_channel(small_mask, small_rgb_image)
        assert result[30, 30] > 0  # Center of masked region

    def test_values_in_valid_range(self, small_mask, small_rgb_image):
        result = refine_alpha_channel(small_mask, small_rgb_image)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_binary_mask_01_scaled(self, small_rgb_image):
        """Mask with values 0/1 (not 0/255) is auto-scaled."""
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[20:44, 20:44] = 1
        result = refine_alpha_channel(mask, small_rgb_image)
        assert result[30, 30] > 0

    def test_rgba_guide_accepted(self, small_mask, small_rgba_image):
        """Guide image can be RGBA — function strips alpha."""
        result = refine_alpha_channel(small_mask, small_rgba_image)
        assert result.shape == small_mask.shape

    def test_grayscale_guide_accepted(self, small_mask):
        """Guide image can be single-channel grayscale."""
        gray = np.random.randint(0, 255, (64, 64), dtype=np.uint8)
        result = refine_alpha_channel(small_mask, gray)
        assert result.shape == small_mask.shape

    def test_3d_mask_handled(self, small_rgb_image):
        """If mask is 3-channel, first channel is used."""
        mask_3ch = np.zeros((64, 64, 3), dtype=np.uint8)
        mask_3ch[20:44, 20:44] = 255
        result = refine_alpha_channel(mask_3ch, small_rgb_image)
        assert result.shape == (64, 64)

    def test_custom_trimap_params(self, small_mask, small_rgb_image):
        """Custom dilate/erode params don't crash."""
        result = refine_alpha_channel(
            small_mask, small_rgb_image, trimap_dilate=5, trimap_erode=3, min_size=50
        )
        assert result.shape == small_mask.shape


# ---------------------------------------------------------------------------
# generate_trimap
# ---------------------------------------------------------------------------
class TestGenerateTrimap:
    def test_output_shape(self, small_mask):
        trimap = generate_trimap(small_mask)
        assert trimap.shape == small_mask.shape

    def test_contains_three_regions(self, small_mask):
        trimap = generate_trimap(small_mask)
        vals = set(np.unique(trimap))
        assert 0 in vals      # background
        assert 255 in vals    # foreground
        assert 128 in vals    # unknown

    def test_all_zero_mask_gives_all_bg(self):
        mask = np.zeros((32, 32), dtype=np.uint8)
        trimap = generate_trimap(mask)
        assert (trimap == 0).all() or (trimap == 128).all()


# ---------------------------------------------------------------------------
# remove_small_islands
# ---------------------------------------------------------------------------
class TestRemoveSmallIslands:
    def test_preserves_large_component(self):
        alpha = np.zeros((64, 64), dtype=np.float32)
        alpha[10:50, 10:50] = 1.0  # large island
        result = remove_small_islands(alpha, min_size=10)
        assert result[30, 30] > 0

    def test_removes_tiny_island(self):
        alpha = np.zeros((64, 64), dtype=np.float32)
        alpha[10:50, 10:50] = 1.0  # large
        alpha[0, 0] = 1.0          # tiny (1px)
        result = remove_small_islands(alpha, min_size=10)
        assert result[0, 0] == 0.0

    def test_keep_largest_only(self):
        alpha = np.zeros((64, 64), dtype=np.float32)
        alpha[5:25, 5:25] = 1.0    # medium
        alpha[35:55, 35:55] = 1.0  # medium
        result = remove_small_islands(alpha, min_size=5, keep_largest_only=True)
        # Only one component should remain
        assert result.sum() < alpha.sum()


# ---------------------------------------------------------------------------
# guided_filter
# ---------------------------------------------------------------------------
class TestGuidedFilter:
    def test_output_shape(self, small_mask, small_rgb_image):
        alpha = small_mask.astype(np.float32) / 255.0
        result = guided_filter(small_rgb_image, alpha)
        assert result.shape == alpha.shape

    def test_output_range(self, small_mask, small_rgb_image):
        alpha = small_mask.astype(np.float32) / 255.0
        result = guided_filter(small_rgb_image, alpha)
        assert result.min() >= 0.0
        assert result.max() <= 1.0


# ---------------------------------------------------------------------------
# count_mask_islands
# ---------------------------------------------------------------------------
class TestCountMaskIslands:
    def test_single_blob_zero_islands(self):
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[10:50, 10:50] = 255
        assert count_mask_islands(mask) == 0

    def test_two_blobs_one_island(self):
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[5:25, 5:25] = 255    # larger
        mask[40:55, 40:55] = 255  # smaller → island
        assert count_mask_islands(mask, min_size=5) == 1

    def test_empty_mask_zero(self):
        mask = np.zeros((32, 32), dtype=np.uint8)
        assert count_mask_islands(mask) == 0

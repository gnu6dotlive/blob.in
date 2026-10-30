"""Independent negative laws for QCHAIN compositor pixel attribution."""
import unittest
from qchain_compositor_gate import WIDTH, HEIGHT, ROUNDING_RADIUS, compare_rgba

class CompositorMaskLawTests(unittest.TestCase):
    def setUp(self):
        self.expected=bytes([21,92,161,255])*(WIDTH*HEIGHT)
    def test_all_exact_pixels_pass_without_masking_need(self):
        result=compare_rgba(self.expected,self.expected)
        self.assertTrue(result["accepted_region_exact"])
        self.assertTrue(result["entire_frame_exact"])
        self.assertEqual(result["excluded_corner_pixels"],4*18*18)
    def test_a_forged_centre_pixel_is_rejected(self):
        fake=bytearray(self.expected)
        pos=((HEIGHT//2)*WIDTH+(WIDTH//2))*4
        fake[pos]^=1
        result=compare_rgba(self.expected,bytes(fake))
        self.assertFalse(result["accepted_region_exact"])
        self.assertEqual(result["different_pixels_outside_corner_mask"],1)
    def test_only_bounded_18px_corner_is_excluded(self):
        fake=bytearray(self.expected)
        fake[0]^=1
        result=compare_rgba(self.expected,bytes(fake))
        self.assertTrue(result["accepted_region_exact"])
        self.assertFalse(result["entire_frame_exact"])
        self.assertEqual(result["different_pixels_total"],1)
    def test_a_pixel_just_outside_corner_square_is_rejected(self):
        fake=bytearray(self.expected)
        fake[((ROUNDING_RADIUS*WIDTH)+0)*4]^=1
        self.assertFalse(compare_rgba(self.expected,bytes(fake))["accepted_region_exact"])
    def test_expanded_or_short_pixel_mask_refused(self):
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_CORNER_MASK"):
            compare_rgba(self.expected,self.expected,19)
        with self.assertRaisesRegex(ValueError,"RGBA_SIZE_MISMATCH"):
            compare_rgba(self.expected,self.expected[:-4])
if __name__=="__main__":
    unittest.main()

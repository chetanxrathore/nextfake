//! Deterministic random number generation and parallel work partitioning.
//!
//! Every generated value is a pure function of `(seed, column stream, chunk index, row offset
//! within the chunk)`. Rows are partitioned into fixed-size chunks of [`CHUNK_ROWS`] rows that do
//! **not** depend on the number of worker threads, and each `(chunk, column)` pair owns an
//! independent [`ChaCha8Rng`] keyed by `(seed, chunk)` with the column's 64-bit stream id selected
//! via ChaCha's native stream parameter. Consequently, a dataset generated with 1 thread is
//! byte-for-byte identical to the same dataset generated with 64 threads on any CPU topology.

use rand_chacha::ChaCha8Rng;
use rand_core::{Rng, SeedableRng};

/// Number of rows per deterministic generation chunk.
///
/// This value is part of the reproducibility contract: changing it changes generated data.
pub const CHUNK_ROWS: usize = 16_384;

/// The RNG used throughout the crate.
pub type FastRng = ChaCha8Rng;

/// SplitMix64 finaliser: a cheap, high-quality 64-bit mixer.
#[inline]
pub const fn splitmix64(mut z: u64) -> u64 {
    z = z.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

/// Stable 64-bit FNV-1a hash used to derive a per-column RNG stream id from its name.
///
/// Deriving the stream from the column *name* (instead of its position) means adding, removing
/// or reordering other columns never changes the values generated for an existing column.
pub fn stream_id(name: &str) -> u64 {
    let mut h: u64 = 0xCBF2_9CE4_8422_2325;
    for b in name.as_bytes() {
        h ^= u64::from(*b);
        h = h.wrapping_mul(0x0000_0100_0000_01B3);
    }
    splitmix64(h)
}

/// Build the RNG for a given `(seed, chunk, stream)` triple.
///
/// The 256-bit ChaCha key embeds `seed` and `chunk` verbatim (plus mixed copies), so distinct
/// `(seed, chunk)` pairs can never collide; `stream` selects one of 2^64 independent streams.
pub fn chunk_rng(seed: u64, chunk: u64, stream: u64) -> FastRng {
    let mut key = [0u8; 32];
    key[0..8].copy_from_slice(&seed.to_le_bytes());
    key[8..16].copy_from_slice(&chunk.to_le_bytes());
    key[16..24].copy_from_slice(&splitmix64(seed ^ 0x6E65_7874_6661_6B65).to_le_bytes());
    key[24..32].copy_from_slice(&splitmix64(chunk.rotate_left(17) ^ seed).to_le_bytes());
    let mut rng = FastRng::from_seed(key);
    rng.set_stream(stream);
    rng
}

/// The sequential "session" RNG used by single-value calls (`Faker.name()` etc.).
pub fn session_rng(seed: u64) -> FastRng {
    chunk_rng(seed, u64::MAX, 0x5E55_1011)
}

/// A fresh, non-deterministic seed from the operating system.
pub fn entropy_seed() -> u64 {
    rand::random::<u64>()
}

/// A contiguous range of rows generated as one deterministic unit.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Chunk {
    /// Chunk index (0-based); part of the RNG key.
    pub index: usize,
    /// Global index of the first row in this chunk.
    pub start: usize,
    /// Number of rows in this chunk (`<= CHUNK_ROWS`).
    pub len: usize,
}

/// Split `count` rows into fixed-size chunks.
pub fn chunks(count: usize) -> Vec<Chunk> {
    (0..count.div_ceil(CHUNK_ROWS))
        .map(|index| {
            let start = index * CHUNK_ROWS;
            Chunk {
                index,
                start,
                len: CHUNK_ROWS.min(count - start),
            }
        })
        .collect()
}

/// Sampling helpers implemented on top of the raw `next_u32`/`next_u64` RNG interface.
///
/// These are implemented locally (rather than via `rand::distr`) so that the exact mapping from
/// RNG words to values is pinned by this crate and cannot drift across dependency upgrades.
pub trait Sample: Rng {
    /// Uniform integer in `0..n` (unbiased, Lemire's multiply-shift with rejection).
    /// Returns 0 when `n == 0`.
    #[inline]
    fn below(&mut self, n: usize) -> usize {
        if n <= 1 {
            return 0;
        }
        if n <= u32::MAX as usize {
            let n32 = n as u32;
            let mut m = u64::from(self.next_u32()) * u64::from(n32);
            let mut low = m as u32;
            if low < n32 {
                let threshold = n32.wrapping_neg() % n32;
                while low < threshold {
                    m = u64::from(self.next_u32()) * u64::from(n32);
                    low = m as u32;
                }
            }
            (m >> 32) as usize
        } else {
            self.below_u64(n as u64) as usize
        }
    }

    /// Uniform integer in `0..n` for 64-bit `n` (`n == 0` means the full `u64` range).
    #[inline]
    fn below_u64(&mut self, n: u64) -> u64 {
        if n == 0 {
            return self.next_u64();
        }
        let mut m = u128::from(self.next_u64()) * u128::from(n);
        let mut low = m as u64;
        if low < n {
            let threshold = n.wrapping_neg() % n;
            while low < threshold {
                m = u128::from(self.next_u64()) * u128::from(n);
                low = m as u64;
            }
        }
        (m >> 64) as u64
    }

    /// Uniform integer in the inclusive range `lo..=hi` (caller guarantees `lo <= hi`).
    #[inline]
    fn range_i64(&mut self, lo: i64, hi: i64) -> i64 {
        let span = (hi as i128 - lo as i128 + 1) as u128;
        if span > u128::from(u64::MAX) {
            return self.next_u64() as i64;
        }
        lo.wrapping_add(self.below_u64(span as u64) as i64)
    }

    /// Uniform `f64` in `[0, 1)` with 53 bits of precision.
    #[inline]
    fn unit_f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }

    /// `true` with probability `p`.
    #[inline]
    fn chance(&mut self, p: f64) -> bool {
        if p <= 0.0 {
            false
        } else if p >= 1.0 {
            true
        } else {
            self.unit_f64() < p
        }
    }

    /// A random decimal digit as an ASCII byte (`b'0'..=b'9'`).
    #[inline]
    fn digit(&mut self) -> u8 {
        b'0' + self.below(10) as u8
    }

    /// Pick a uniformly random element of a non-empty slice.
    #[inline]
    fn pick<'a, T>(&mut self, items: &'a [T]) -> &'a T {
        &items[self.below(items.len())]
    }
}

impl<R: Rng + ?Sized> Sample for R {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn chunking_covers_all_rows() {
        for count in [
            0,
            1,
            CHUNK_ROWS - 1,
            CHUNK_ROWS,
            CHUNK_ROWS + 1,
            5 * CHUNK_ROWS + 7,
        ] {
            let cs = chunks(count);
            assert_eq!(cs.iter().map(|c| c.len).sum::<usize>(), count);
            for (i, c) in cs.iter().enumerate() {
                assert_eq!(c.index, i);
                assert_eq!(c.start, i * CHUNK_ROWS);
            }
        }
    }

    #[test]
    fn chunk_rng_is_deterministic_and_distinct() {
        let mut a = chunk_rng(42, 3, 7);
        let mut b = chunk_rng(42, 3, 7);
        let mut c = chunk_rng(42, 4, 7);
        let mut d = chunk_rng(42, 3, 8);
        let va: Vec<u64> = (0..16).map(|_| a.next_u64()).collect();
        let vb: Vec<u64> = (0..16).map(|_| b.next_u64()).collect();
        let vc: Vec<u64> = (0..16).map(|_| c.next_u64()).collect();
        let vd: Vec<u64> = (0..16).map(|_| d.next_u64()).collect();
        assert_eq!(va, vb);
        assert_ne!(va, vc);
        assert_ne!(va, vd);
    }

    #[test]
    fn sampling_bounds() {
        let mut rng = chunk_rng(1, 0, 0);
        for _ in 0..10_000 {
            assert!(rng.below(7) < 7);
            let v = rng.range_i64(-5, 5);
            assert!((-5..=5).contains(&v));
            let f = rng.unit_f64();
            assert!((0.0..1.0).contains(&f));
        }
        assert_eq!(rng.below(0), 0);
        assert_eq!(rng.below(1), 0);
        // full range must not panic
        let _ = rng.range_i64(i64::MIN, i64::MAX);
    }

    #[test]
    fn below_is_roughly_uniform() {
        let mut rng = chunk_rng(9, 9, 9);
        let mut counts = [0usize; 10];
        for _ in 0..100_000 {
            counts[rng.below(10)] += 1;
        }
        for c in counts {
            assert!((9_000..11_000).contains(&c), "{counts:?}");
        }
    }

    #[test]
    fn stream_ids_differ() {
        assert_ne!(stream_id("email"), stream_id("emails"));
        assert_eq!(stream_id("id"), stream_id("id"));
    }
}

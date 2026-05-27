# GPP Response Trend Diagnostic Checks

## Key Checks
- flash_SMrz: response_detected unique=0,1; event year range=1982-2022
- flash_SMs: response_detected unique=0,1; event year range=1982-2022
- nonflash_SMrz: response_detected unique=0,1; event year range=1982-2022
- nonflash_SMs: response_detected unique=0,1; event year range=1982-2022

## Interpretation
- Current `response_rate` is event response proportion: response_count / events (not speed).
- Boundary-year sensitivity test (1983-2021) keeps similar negative slope, so trend is not dominated by only boundary years.
- Added `response_speed_proxy = 1 / t_response_mean` for speed interpretation (smaller t_response = faster).
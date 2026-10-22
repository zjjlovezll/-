SDITT FT-Modal real run, CR400 07(009) straight turnout, 350 km/h
MATLAB R2024b, SDITT_CR400_NoStrTIrr_250728_Face.m unmodified
(Type_Track=FT-Modal, Int_Method=Park, Vlc=350/3.6, Type_simulation=Cal, Mat_FT_S8b.mat 6204 modes)

start 2026-10-21 15:06:04
stop  2026-10-21 17:03:32   (stopped by plan after 104.395 m; planned end ~115.6 m)
wall  7047 s
travel 32.004 -> 104.395 m  = 72.391 m
simulated time 0.7446 s at 97.22 m/s
realtime factor 9465 x
steps ~7448 (9.72 mm/step)  ->  ~0.95 s wall per step

Velch comparison (same vehicle, same turnout, 350 km/h):
  modal320 (355 DOF): 43.9 s wall for 0.05 s simulated -> 828 x realtime, 9.03 s per metre
  ratio: ~11 x cheaper per simulated second, ~38 x cheaper per step

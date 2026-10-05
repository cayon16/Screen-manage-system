@echo off
rem Chay PentaSync voi thoi gian cho NGAN de test nhanh.
rem KHONG dung file nay khi chay that - chay that thi mo thang PentaSync.exe.
rem   - im lang 10 giay: hoi "ban con o day khong?"
rem   - them 10 giay: tu ket thuc doan chat
rem   - 30 giay khong ai cham: ca he thong ve video cho
set PENTASYNC_TIER1_WARNING_SEC=10
set PENTASYNC_TIER1_CLEANUP_SEC=10
set PENTASYNC_TIER2_CLUSTER_IDLE_SEC=30
start "" "%~dp0PentaSync.exe"

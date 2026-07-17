@echo off
cd /d "Z:\proj\bob02\archive\Sony\bob02\BOB_206"
for %%d in (
    BOB_206_013_020
    BOB_206_018_010
    BOB_206_035_003
    BOB_206_035_140
    BOB_206_A22_010
    BOB_206_B22_020
    BOB_206_B22_030
) do (
    if exist "%%~d" (
        echo Deleting "%%~d"...
        rmdir /s /q "%%~d"
    ) else (
        echo "%%~d" not found.
    )
)
echo Done!


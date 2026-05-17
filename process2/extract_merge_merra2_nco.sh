#!/usr/bin/env bash
set -euo pipefail

# 用法:
#   bash extract_merge_merra2_nco.sh [INPUT_DIR] [OUTPUT_DIR]
# 示例:
#   bash extract_merge_merra2_nco.sh /data/MERRA2 /home/xulc/flash_drought/gleam/result

INPUT_DIR="${1:-/data/MERRA2}"
OUTPUT_DIR="${2:-/home/xulc/flash_drought/gleam/result}"

OUT_RZ_DIR="${OUTPUT_DIR}/SMrz_MERRA2_1"
OUT_SF_DIR="${OUTPUT_DIR}/SMs_MERRA2_1"
RZ_OUT="${OUT_RZ_DIR}/SMrz_MERRA2_1980_2024_daily.nc4"
SF_OUT="${OUT_SF_DIR}/SMs_MERRA2_1980_2024_daily.nc4"

TMP_DIR="${OUTPUT_DIR}/.tmp_merra2_nco"
TMP_RZ="${TMP_DIR}/RZMC"
TMP_SF="${TMP_DIR}/SFMC"
LIST_FILE="${TMP_DIR}/merra2_files.txt"

mkdir -p "${OUT_RZ_DIR}" "${OUT_SF_DIR}" "${TMP_RZ}" "${TMP_SF}"

for cmd in ncks ncrcat; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "错误: 未找到 $cmd，请先安装 NCO。"
    exit 1
  fi
done

find "${INPUT_DIR}" -maxdepth 1 -type f -name 'MERRA2_*.tavg1_2d_lnd_Nx.*.nc4' | sort > "${LIST_FILE}"
if [[ ! -s "${LIST_FILE}" ]]; then
  echo "错误: 在 ${INPUT_DIR} 未找到匹配文件 MERRA2_*.tavg1_2d_lnd_Nx.*.nc4"
  exit 1
fi

FIRST_FILE="$(head -n 1 "${LIST_FILE}")"
if ! ncks -m -v RZMC "$FIRST_FILE" >/dev/null 2>&1; then
  echo "错误: 文件中未检测到变量 RZMC: $FIRST_FILE"
  exit 1
fi
if ! ncks -m -v SFMC "$FIRST_FILE" >/dev/null 2>&1; then
  echo "错误: 文件中未检测到变量 SFMC: $FIRST_FILE"
  exit 1
fi

echo "[1/4] 提取 RZMC/SFMC 单变量文件..."
while IFS= read -r f; do
  b="$(basename "$f")"
  # 保留 time/lat/lon 坐标与目标变量，减小后续合并压力
  ncks -O -4 -L 4 -v time,lat,lon,RZMC "$f" "${TMP_RZ}/${b}"
  ncks -O -4 -L 4 -v time,lat,lon,SFMC "$f" "${TMP_SF}/${b}"
done < "${LIST_FILE}"

echo "[2/4] 按时间拼接 RZMC ..."
# ncrcat 会沿 record dimension (time) 拼接
ncrcat -O -4 -L 4 "${TMP_RZ}"/*.nc4 "${RZ_OUT}"

echo "[3/4] 按时间拼接 SFMC ..."
ncrcat -O -4 -L 4 "${TMP_SF}"/*.nc4 "${SF_OUT}"

echo "[4/4] 结果检查..."
echo "RZMC 输出: ${RZ_OUT}"
ncks -m "${RZ_OUT}" | sed -n '1,40p'

echo "SFMC 输出: ${SF_OUT}"
ncks -m "${SF_OUT}" | sed -n '1,40p'

echo "完成。临时目录: ${TMP_DIR}"
echo "确认无误后可删除临时目录: rm -rf ${TMP_DIR}"

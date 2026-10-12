WITH dates AS (
  SELECT EXPLODE(SEQUENCE(DATE'2026-10-01', DATE'2026-10-11', INTERVAL 1 DAY)) AS dt
), audit_logs_data_1 AS (
  SELECT
    datestr AS dt,
    store_id,
    sku_id,
    process_id AS inbound_code,
    from_bin,
    to_bin,
    SUM(transaction_qty) AS qty
  FROM silver.thor_core.inventory_audit_logs AS ma
  WHERE
    datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND (
      (
        UPPER(ma.from_bin) IN (
          'RETURN_QC_PASS',
          'STAGING',
          'CAFE-STAGEBIN',
          'PHARMA-STAGE-BIN',
          'EXCESSLPNBIN',
          'CAFE-EXCESSLPNBIN',
          'PHARMA-EXCESSLPNBIN'
        )
      )
      AND (
        UPPER(ma.to_bin) IN ('DSSHORTBIN', 'IBSHORTBIN', 'CAFE-IBSHORTBIN', 'PHARMA-SHORT-BIN')
      )
    )
  GROUP BY ALL
), free_pick_audit AS (
  SELECT
    datestr AS dt,
    dbObject_storeId,
    dbObject_skuId AS sku_id,
    dbObject_fromBin,
    dbObject_fromBinId,
    dbObject_toBinId,
    SUM(dbObject_transactionQty) AS qty
  FROM silver.thor_audit.inventory_movement_audit_vw
  WHERE
    TRUE
    AND dbObject_fromBin = 'FREE_PICK_BIN'
    AND datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND dbObject_flow = 'OUT'
  GROUP BY ALL
), base_data AS (
  SELECT
    r.order_date AS dt,
    sf.city_name,
    sf.store_name,
    r.sku AS sku_id,
    CASE WHEN sf.sub_type = 'SUPERSTORE' THEN 'SUPERSTORE' ELSE 'RETAIL_STORE' END AS store_sub_type,
    COALESCE(cf.cogs, 97) AS cogs_,
    (
      irsku_total_qty - handshake_qty
    ) AS hs_qty,
    (
      (
        received_qty - good_putaway_qty - Bad_Putaway_Quantity
      ) + Short_Receiving + Short_Putaway + (
        handshake_qty - (
          CASE
            WHEN COALESCE(qc_eligible_flag, '') = 'false'
            THEN handshake_qty
            ELSE received_qty + Bad_Recieved_qty
          END
        )
      )
    ) AS dh_qty
  FROM gold.ops.wms_rto_sku_tracking_v2 AS r
  LEFT JOIN gold.zepto.store_fact AS sf
    ON sf.store_id = r.store_id
  LEFT JOIN gold.ops.city_sku_cogs_fact AS cf
    ON sf.city_name = cf.city_name AND r.sku = cf.sku
  WHERE
    order_date BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND NOT category_name IN ('Zepto Cafe', 'Unlisted1')
), audit_logs_data_1_excess AS (
  SELECT
    datestr AS dt,
    dbObject_storeId,
    dbObject_skuId AS sku_id,
    dbObject_fromBin,
    dbObject_fromBinId,
    dbObject_toBinId,
    SUM(-1 * dbObject_transactionQty) AS qty
  FROM silver.thor_audit.inventory_movement_audit_vw AS ma
  WHERE
    datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND (
      dbObject_flow = 'ADJUSTMENT'
      AND (
        dbObject_movementType IN (
          'EXCESS_SKU_DAMAGE_REMOVAL',
          'EXCESS_SKU_DAMAGE_SCRAP_REMOVAL',
          'EXCESS_SKU_EXPIRY_LIQUIDATION_REMOVAL',
          'EXCESS_SKU_EXPIRY_REMOVAL',
          'EXCESS_SKU_EXPIRY_SCRAP_REMOVAL',
          'EXCESS_SKU_QUALITY_REMOVAL',
          'INBOUND_PUTAWAY_LPN_REPORT_EXCESS'
        )
        OR dbObject_movementType ILIKE '%excess%'
      )
      AND COALESCE(REGEXP_EXTRACT(dbObject_remarks, 'lpnNumber\\s*-\\s*([A-Z0-9-]+)'), '') <> ''
    )
    AND dbObject_transactionQty <> 0
  GROUP BY ALL
), audit_logs_data_3 AS (
  SELECT
    datestr AS dt,
    dbObject_storeId,
    dbObject_skuId AS sku_id,
    dbObject_fromBin,
    dbObject_fromBinId,
    dbObject_toBinId,
    SUM(dbObject_transactionQty) AS qty
  FROM silver.thor_audit.inventory_movement_audit_vw AS ma
  WHERE
    datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND dbObject_toBin IN ('SHORTPICKBIN', 'SHORTSORTBIN', 'CAFE-SHORTPICKBIN', 'IBSHORTBIN')
    AND dbObject_transactionQty <> 0
  GROUP BY ALL
), audit_logs_data_2 AS (
  SELECT
    datestr AS dt,
    dbObject_storeId,
    dbObject_skuId AS sku_id,
    dbObject_fromBin,
    dbObject_fromBinId,
    SUM(-1 * dbObject_transactionQty) AS qty
  FROM silver.thor_audit.inventory_movement_audit_vw AS ma
  WHERE
    datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND dbObject_flow = 'ADJUSTMENT'
    AND NOT dbObject_movementType IN ('THOR_MIGRATION', 'PUTAWAY_INBOUND')
    AND dbObject_transactionQty <> 0
    AND NOT dbObject_movementType ILIKE '%excess%'
  GROUP BY ALL
), adjust_lpn AS (
  SELECT
    datestr AS dt,
    dbObject_storeId,
    dbObject_skuId AS sku_id,
    dbObject_fromBin,
    dbObject_fromBinId,
    SUM(-1 * dbObject_transactionQty) AS qty
  FROM silver.thor_audit.inventory_movement_audit_vw AS ma
  WHERE
    datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND dbObject_flow = 'ADJUST_LPN'
    AND NOT dbObject_movementType IN ('THOR_MIGRATION', 'PUTAWAY_INBOUND')
    AND dbObject_transactionQty <> 0
    AND NOT dbObject_movementType ILIKE '%excess%'
  GROUP BY ALL
), cte AS (
  SELECT
    datestr AS created_on,
    dbObject_skuId AS sku_id,
    dbObject_storeId AS store_id,
    SUM(-1 * dbObject_transactionQty) AS qty
  FROM silver.thor_audit.inventory_movement_audit_vw
  WHERE
    1 = 1
    AND datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND dbObject_fromBin IN ('EXCESSBIN', 'QC_EXCESS_BIN')
    AND NOT dbObject_toBinId IS NULL
  GROUP BY ALL
), cte2 AS (
  SELECT
    datestr AS created_on,
    dbObject_skuId AS sku_id,
    dbObject_storeId AS store_id,
    SUM(dbObject_transactionQty) AS qty
  FROM silver.thor_audit.inventory_movement_audit_vw
  WHERE
    1 = 1
    AND datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
    AND dbObject_toBin = 'FCCBIN'
  GROUP BY ALL
)
SELECT
  v.dt AS Date,
  COALESCE(m.leader, 'Not Mapped') AS Leader,
  COALESCE(m.clm, 'Not Mapped') AS CLM,
  v.store AS Store,
  CASE
    WHEN UPPER(v.storage_zone) LIKE '%CHILL%' THEN 'Chiller'
    WHEN UPPER(v.storage_zone) LIKE '%FREEZ%' OR UPPER(v.storage_zone) LIKE '%FROZEN%' THEN 'Freezer'
    WHEN UPPER(v.storage_zone) LIKE '%AMBIENT%' THEN 'Ambient'
    WHEN UPPER(v.storage_zone) LIKE '%DRY%' THEN 'Dry'
    ELSE 'Others'
  END AS Storage_Zone,
  ROUND(SUM(CASE WHEN v.type = 'Adj' THEN v.val ELSE 0 END), 0) AS Adj,
  ROUND(SUM(CASE WHEN v.type = 'FCC' THEN v.val ELSE 0 END), 0) AS FCC,
  ROUND(SUM(CASE WHEN v.type = 'Proj_PA_ClosureD0' THEN v.val ELSE 0 END), 0) AS Proj_PA_ClosureD0,
  ROUND(SUM(CASE WHEN v.type = 'PUTAWAY_CLOSURE' THEN v.val ELSE 0 END), 0) AS PUTAWAY_CLOSURE,
  ROUND(SUM(CASE WHEN v.type = 'RTO_DH' THEN v.val ELSE 0 END), 0) AS RTO_DH,
  ROUND(SUM(CASE WHEN v.type = 'RTO_HS' THEN v.val ELSE 0 END), 0) AS RTO_HS,
  ROUND(SUM(CASE WHEN v.type = 'Shortpick' THEN v.val ELSE 0 END), 0) AS Shortpick,
  ROUND(SUM(v.val), 0) AS Grand_Total
FROM (
  SELECT
    a.day AS dt,
    b.Zone AS zone,
    city_name AS city,
    store AS store,
    LOWER(sku_id) AS sku_id,
    d.storage_zone AS storage_zone,
    store_sub_type AS store_type,
    type_movement AS type,
    zone_sheet.Total AS target,
    zone_sheet.InTransit AS zoneInTransit_target,
    zone_sheet.DH_IH AS zoneDH_IH_target,
    zone_sheet.MH_IH AS zoneMH_IH_target,
    city_sheet.Total AS city_target,
    city_sheet.InTransit AS cityInTransit_target,
    city_sheet.DH_IH AS cityDH_IH_target,
    city_sheet.MH_IH AS cityMH_IH_target,
    SUM(value) AS val,
    SUM(qty) AS qty
  FROM (
    SELECT
      CAST(u.dt AS DATE) AS day,
      'Shortage' AS type_movement,
      store_name AS store,
      u.sku_id,
      l.city_name,
      SUM(CASE WHEN to_bin = 'IBSHORTBIN' AND store_type = 'WAREHOUSE' THEN 0 ELSE qty END) AS qty,
      CONCAT('InTransit Short', '-', L.store_type) AS store_sub_type,
      cogs,
      SUM(
        CASE
          WHEN to_bin = 'IBSHORTBIN' AND store_type = 'WAREHOUSE'
          THEN 0
          ELSE (
            qty * cogs
          )
        END
      ) AS value,
      store_type
    FROM audit_logs_data_1 AS u
    LEFT JOIN gold.zepto.sku_info AS s
      ON LOWER(s.product_variant_id) = LOWER(u.sku_id)
    JOIN gold.zepto.store_fact AS l
      ON (
        l.store_id = u.store_id
      )
    LEFT JOIN gold.ops.city_sku_cogs_fact AS csc
      ON csc.city_name = l.city_name AND LOWER(csc.sku) = LOWER(s.product_variant_id)
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(u.dt AS DATE) AS day,
      'Excess New FWD' AS type_movement,
      store_name AS store,
      u.sku_id,
      l.city_name,
      SUM(qty) AS qty,
      'Excess New FWD' AS store_sub_type,
      cogs,
      SUM(qty * cogs) AS value,
      store_type
    FROM audit_logs_data_1_excess AS u
    LEFT JOIN gold.zepto.sku_info AS s
      ON LOWER(s.product_variant_id) = LOWER(u.sku_id)
    JOIN gold.zepto.store_fact AS l
      ON (
        l.store_id = u.dbObject_storeId
      )
    LEFT JOIN gold.ops.city_sku_cogs_fact AS csc
      ON csc.city_name = l.city_name AND LOWER(csc.sku) = LOWER(s.product_variant_id)
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
      AND l.store_type <> 'WAREHOUSE'
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(u.dt AS DATE) AS day,
      'Excess New RV' AS type_movement,
      store_name AS store,
      u.sku_id,
      l.city_name,
      SUM(qty) AS qty,
      'Excess New RV' AS store_sub_type,
      cogs,
      SUM(qty * cogs) AS value,
      store_type
    FROM audit_logs_data_1_excess AS u
    LEFT JOIN gold.zepto.sku_info AS s
      ON LOWER(s.product_variant_id) = LOWER(u.sku_id)
    JOIN gold.zepto.store_fact AS l
      ON (
        l.store_id = u.dbObject_storeId
      )
    LEFT JOIN gold.ops.city_sku_cogs_fact AS csc
      ON csc.city_name = l.city_name AND LOWER(csc.sku) = LOWER(s.product_variant_id)
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
      AND l.store_type = 'WAREHOUSE'
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(u.dt AS DATE) AS day,
      'Adj' AS type_movement,
      store_name AS store,
      u.sku_id,
      l.city_name,
      SUM(qty) AS qty,
      CASE
        WHEN l.store_name LIKE '%SS-MH%'
        THEN 'dry'
        WHEN l.store_name = 'GUR-SS_DRY_MH_SILANI _ZL'
        THEN 'dry'
        WHEN l.sub_type = 'SUPERSTORE'
        THEN 'SUPERSTORE'
        WHEN l.store_type = 'RETAIL_STORE'
        THEN 'RETAIL_STORE'
        WHEN l.store_name LIKE '%PHARMA%'
        THEN 'PHARMA_WAREHOUSE'
        WHEN NOT l.store_category IS NULL
        THEN l.store_category
        ELSE store_type
      END AS store_sub_type,
      cogs,
      SUM(qty * cogs) AS value,
      store_type
    FROM audit_logs_data_2 AS u
    LEFT JOIN gold.zepto.sku_info AS s
      ON LOWER(s.product_variant_id) = LOWER(u.sku_id)
    JOIN gold.zepto.store_fact AS l
      ON (
        l.store_id = u.dbobject_storeid
      )
    LEFT JOIN gold.ops.city_sku_cogs_fact AS csc
      ON csc.city_name = l.city_name AND LOWER(csc.sku) = LOWER(s.product_variant_id)
    JOIN silver.thor_core.bins AS b
      ON b.id = dbObject_fromBinId
      AND b.bin_type IN ('Good', 'Deep')
      AND b.bin_code <> 'RTV-P2DCANCEL-BIN'
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(u.dt AS DATE) AS day,
      'Adjust_LPN_Shrinkage' AS type_movement,
      store_name AS store,
      u.sku_id,
      l.city_name,
      SUM(qty) AS qty,
      CASE
        WHEN l.store_name LIKE '%SS-MH%'
        THEN 'dry'
        WHEN l.sub_type = 'SUPERSTORE'
        THEN 'SUPERSTORE'
        WHEN l.store_type = 'RETAIL_STORE'
        THEN 'RETAIL_STORE'
        WHEN l.store_name LIKE '%PHARMA%'
        THEN 'PHARMA_WAREHOUSE'
        WHEN NOT l.store_category IS NULL
        THEN l.store_category
        ELSE store_type
      END AS store_sub_type,
      cogs,
      SUM(qty * cogs) AS value,
      store_type
    FROM free_pick_audit AS u
    LEFT JOIN gold.zepto.sku_info AS s
      ON LOWER(s.product_variant_id) = LOWER(u.sku_id)
    JOIN gold.zepto.store_fact AS l
      ON (
        l.store_id = u.dbobject_storeid
      )
    LEFT JOIN gold.ops.city_sku_cogs_fact AS csc
      ON csc.city_name = l.city_name AND LOWER(csc.sku) = LOWER(s.product_variant_id)
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(u.dt AS DATE) AS day,
      'Adjust_LPN' AS type_movement,
      store_name AS store,
      u.sku_id,
      l.city_name,
      SUM(qty) AS qty,
      CASE
        WHEN l.store_name LIKE '%SS-MH%'
        THEN 'dry'
        WHEN l.sub_type = 'SUPERSTORE'
        THEN 'SUPERSTORE'
        WHEN l.store_type = 'RETAIL_STORE'
        THEN 'RETAIL_STORE'
        WHEN l.store_name LIKE '%PHARMA%'
        THEN 'PHARMA_WAREHOUSE'
        WHEN NOT l.store_category IS NULL
        THEN l.store_category
        ELSE store_type
      END AS store_sub_type,
      cogs,
      SUM(qty * cogs) AS value,
      store_type
    FROM adjust_lpn AS u
    LEFT JOIN gold.zepto.sku_info AS s
      ON LOWER(s.product_variant_id) = LOWER(u.sku_id)
    JOIN gold.zepto.store_fact AS l
      ON (
        l.store_id = u.dbobject_storeid
      )
    LEFT JOIN gold.ops.city_sku_cogs_fact AS csc
      ON csc.city_name = l.city_name AND LOWER(csc.sku) = LOWER(s.product_variant_id)
    JOIN silver.thor_core.bins AS b
      ON b.id = dbObject_fromBinId
      AND /* and b.bin_type in ('Good', 'Deep') */ b.bin_code <> 'RTV-P2DCANCEL-BIN'
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(c.created_on AS DATE) AS day,
      'Excess Old' AS type_movement,
      store_name AS store,
      c.sku_id,
      s.city_name,
      SUM(qty) AS qty,
      CASE
        WHEN s.store_name LIKE '%SS-MH%'
        THEN 'dry'
        WHEN sub_type = 'SUPERSTORE'
        THEN 'SUPERSTORE'
        WHEN store_type = 'RETAIL_STORE'
        THEN 'RETAIL_STORE'
        WHEN store_name LIKE '%PHARMA%'
        THEN 'PHARMA_WAREHOUSE'
        WHEN NOT s.store_category IS NULL
        THEN s.store_category
        ELSE store_type
      END AS store_sub_type,
      cogs,
      SUM(qty * cogs) AS value,
      store_type
    FROM cte AS c
    JOIN gold.zepto.store_fact AS s
      ON c.store_id = s.store_id
    LEFT JOIN gold.zepto.sku_info AS i
      ON LOWER(c.sku_id) = LOWER(i.product_variant_id)
    LEFT JOIN gold.ops.city_sku_cogs_fact AS cf
      ON LOWER(cf.sku) = LOWER(c.sku_id) AND s.city_name = cf.city_name
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(u.dt AS DATE) AS day,
      'Shortpick' AS type_movement,
      store_name AS store,
      u.sku_id,
      l.city_name,
      SUM(qty) AS qty,
      CASE
        WHEN l.store_name LIKE '%SS-MH%'
        THEN 'dry'
        WHEN l.store_name = 'GUR-SS_DRY_MH_SILANI _ZL'
        THEN 'dry'
        WHEN sub_type = 'SUPERSTORE'
        THEN 'SUPERSTORE'
        WHEN l.store_type = 'RETAIL_STORE'
        THEN 'RETAIL_STORE'
        WHEN l.store_name LIKE '%PHARMA%'
        THEN 'PHARMA_WAREHOUSE'
        WHEN NOT l.store_category IS NULL
        THEN l.store_category
      END AS store_sub_type,
      cogs,
      SUM(qty * cogs) AS value,
      store_type
    FROM audit_logs_data_3 AS u
    LEFT JOIN gold.zepto.sku_info AS s
      ON LOWER(s.product_variant_id) = LOWER(u.sku_id)
    JOIN gold.zepto.store_fact AS l
      ON (
        l.store_id = u.dbobject_storeid
      )
    LEFT JOIN gold.ops.city_sku_cogs_fact AS csc
      ON csc.city_name = l.city_name AND LOWER(csc.sku) = LOWER(s.product_variant_id)
    JOIN silver.thor_core.bins AS b
      ON dbObject_fromBinId = b.id
      AND (
        (
          b.bin_type IN ('Good') AND bin_code <> 'IBSHORTBIN'
        )
        OR bin_code IN ('SORTBIN', 'PACKBIN_GOOD')
        OR (
          dbObject_fromBin = 'neostationbin' AND bin_code = 'IBSHORTBIN'
        )
      )
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(c.created_on AS DATE) AS day,
      'FCC' AS type_movement,
      store_name AS store,
      c.sku_id,
      s.city_name,
      SUM(qty) AS qty,
      CASE
        WHEN s.store_name LIKE '%SS-MH%'
        THEN 'dry'
        WHEN sub_type = 'SUPERSTORE'
        THEN 'SUPERSTORE'
        WHEN s.store_type = 'RETAIL_STORE'
        THEN 'RETAIL_STORE'
        WHEN s.store_name LIKE '%PHARMA%'
        THEN 'PHARMA_WAREHOUSE'
        WHEN NOT s.store_category IS NULL
        THEN s.store_category
      END AS store_sub_type,
      cogs,
      SUM(qty * cogs) AS value,
      store_type
    FROM cte2 AS c
    LEFT JOIN gold.zepto.store_fact AS s
      ON c.store_id = s.store_id
    LEFT JOIN gold.zepto.sku_info AS i
      ON LOWER(c.sku_id) = LOWER(i.product_variant_id)
    LEFT JOIN gold.ops.city_sku_cogs_fact AS cf
      ON LOWER(cf.sku) = LOWER(c.sku_id) AND s.city_name = cf.city_name
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(txn_closed_on AS DATE) AS day,
      'NYR' AS type_movement,
      destination AS store,
      sku AS sku_id,
      destination_city_name,
      SUM(COALESCE(nyr_sto, 0)) AS qty,
      'InTransit NYR' AS store_sub_type,
      cogs,
      SUM(COALESCE(nyr_sto_amt, 0)) AS val,
      destination_type
    FROM gold.ops.shrinkage_raw_nyr_against_sto
    WHERE
      txn_closed_on BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
      AND NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(c.datestr AS DATE) AS day,
      CASE
        WHEN process_type = 'INPROGRESS_BIN_AGEING_SHRINKAGE'
        THEN 'INPROGRESS_BIN'
        ELSE 'PUTAWAY_CLOSURE'
      END AS type_movement,
      s.store_name AS store,
      c.sku_id AS sku_id,
      s.city_name AS city,
      SUM(transaction_qty) AS qty,
      CASE
        WHEN s.store_name LIKE '%SS-MH%'
        THEN 'dry'
        WHEN sub_type = 'SUPERSTORE'
        THEN 'SUPERSTORE'
        WHEN s.store_type = 'RETAIL_STORE'
        THEN 'RETAIL_STORE'
        WHEN s.store_name LIKE '%PHARMA%'
        THEN 'PHARMA_WAREHOUSE'
        WHEN NOT s.store_category IS NULL
        THEN s.store_category
      END AS store_sub_type,
      transaction_qty_cost / transaction_qty AS cogs,
      SUM(transaction_qty_cost) AS value,
      s.store_type
    FROM gold.product.shrinkage_txns_closure_tracking AS c
    LEFT JOIN gold.zepto.store_fact AS s
      ON c.store_id = s.store_id
    WHERE
      process_type IN (
        'INPROGRESS_BIN_AGEING_SHRINKAGE',
        'P2D_CANCELLATION_SHRINKAGE',
        'SHRINKAGE_PUTAWAY_INVENTORY',
        'SHRINKAGE'
      )
      AND NOT txn_type IN ('Customer_RTO_RnR', 'DH_to_Customer')
      AND NOT from_bin IN ('RETURN-STAGE-BIN', 'FREE_PICK_BIN')
      AND datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
      AND NOT category_name IN ('Zepto Cafe', 'Unlisted1', 'Sample Box')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(u.dt AS DATE) AS day,
      'Fresh_IB_Short' AS type_movement,
      store_name AS store,
      u.sku_id,
      l.city_name,
      SUM(
        CASE WHEN to_bin = 'IBSHORTBIN' AND l.store_type = 'WAREHOUSE' THEN qty ELSE 0 END
      ) AS qty,
      CASE
        WHEN l.store_name LIKE '%SS-MH%'
        THEN 'dry'
        WHEN sub_type = 'SUPERSTORE'
        THEN 'SUPERSTORE'
        WHEN l.store_type = 'RETAIL_STORE'
        THEN 'RETAIL_STORE'
        WHEN l.store_name LIKE '%PHARMA%'
        THEN 'PHARMA_WAREHOUSE'
        WHEN NOT l.store_category IS NULL
        THEN l.store_category
      END AS store_sub_type,
      cogs,
      SUM(
        CASE
          WHEN to_bin = 'IBSHORTBIN' AND l.store_type = 'WAREHOUSE'
          THEN (
            qty * cogs
          )
          ELSE 0
        END
      ) AS value,
      store_type
    FROM audit_logs_data_1 AS u
    LEFT JOIN gold.zepto.sku_info AS s
      ON LOWER(s.product_variant_id) = LOWER(u.sku_id)
    JOIN gold.zepto.store_fact AS l
      ON (
        l.store_id = u.store_id
      )
    LEFT JOIN gold.ops.city_sku_cogs_fact AS csc
      ON csc.city_name = l.city_name AND LOWER(csc.sku) = LOWER(s.product_variant_id)
    WHERE
      NOT category_name IN ('Unlisted1', 'Sample Box', 'Zepto Cafe')
    GROUP BY ALL
    UNION ALL
    SELECT
      CAST(dt AS DATE) AS day,
      'RTO_DH' AS type_movement,
      store_name,
      sku_id,
      city_name,
      SUM(dh_qty) AS qty,
      store_sub_type,
      ROUND(AVG(cogs_), 2) AS cogs,
      SUM(dh_qty * cogs_) AS val,
      'RETAIL_STORE' AS store_type
    FROM base_data
    GROUP BY ALL
    HAVING
      SUM(dh_qty * cogs_) > 0
    UNION ALL
    SELECT
      CAST(dt AS DATE) AS day,
      'RTO_HS' AS type_movement,
      store_name,
      sku_id,
      city_name,
      SUM(hs_qty) AS qty,
      store_sub_type,
      ROUND(AVG(cogs_), 2) AS cogs,
      SUM(hs_qty * cogs_) AS val,
      'RETAIL_STORE' AS store_type
    FROM base_data
    GROUP BY ALL
    HAVING
      SUM(hs_qty * cogs_) > 0
    UNION ALL
    SELECT
      report_dt AS day,
      'Proj_PA_ClosureD0' AS bucket,
      store_name,
      sku,
      city_name,
      SUM(`pending_putaway_PO`) - SUM(COALESCE(`txn_qty`, 0)) AS qty,
      store_sub_type,
      ROUND(AVG(cogs), 2) AS cogs,
      SUM(`pending_pa_po_amt`) - SUM(COALESCE(`txn_val`, 0)) AS val,
      store_type
    FROM (
      SELECT
        dd.dt AS report_dt,
        c.*
        EXCEPT (city_name, locationtype),
        l.store_type,
        CASE
          WHEN l.store_name LIKE '%SS-MH%'
          THEN 'dry'
          WHEN l.store_name = 'GUR-SS_DRY_MH_SILANI _ZL'
          THEN 'dry'
          WHEN l.sub_type = 'SUPERSTORE'
          THEN 'SUPERSTORE'
          WHEN l.store_type = 'RETAIL_STORE'
          THEN 'RETAIL_STORE'
          WHEN l.store_name LIKE '%PHARMA%'
          THEN 'PHARMA_WAREHOUSE'
          WHEN NOT l.store_category IS NULL
          THEN l.store_category
          ELSE l.store_type
        END AS store_sub_type,
        l.city_name,
        t.txn_val,
        t.txn_qty
      FROM gold.ops.shrinkage_raw_pp_against_po AS c
      JOIN dates AS dd
        ON c.inb_use_date >= DATE_SUB(dd.dt, 15)
        AND c.inb_use_date < DATE_SUB(dd.dt, 14)
      LEFT JOIN gold.zepto.store_fact AS l
        ON c.store_name = l.store_name
      LEFT JOIN (
        SELECT
          CAST(datestr AS DATE) AS t_dt,
          store_name,
          sku_id,
          SUM(COALESCE(transaction_qty_cost, 0)) AS txn_val,
          SUM(COALESCE(transaction_qty, 0)) AS txn_qty
        FROM gold.product.shrinkage_txns_closure_tracking AS t
        WHERE
          txn_type IN ('External_PO')
          AND NOT from_bin IN ('RETURN-STAGE-BIN')
          AND datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
          AND NOT category_name IN ('Zepto Cafe', 'Unlisted1', 'Sample Box')
        GROUP BY ALL
      ) AS t
        ON t.store_name = c.store_name AND LOWER(c.sku) = t.sku_id AND t.t_dt = dd.dt
      WHERE
        (c.txn_closed_on IS NULL OR CAST(c.txn_closed_on AS DATE) >= dd.dt)
        AND c.inb_use_date >= DATE'2026-09-16'
        AND c.inb_use_date < DATE'2026-09-27'
    ) AS `virtual_table`
    GROUP BY ALL
    UNION ALL
    SELECT
      report_dt AS day,
      'Proj_PA_ClosureD0' AS bucket,
      store_name,
      sku,
      city_name,
      CASE
        WHEN (
          SUM(`pending_pa_can_sto_rsto`) - SUM(COALESCE(`txn_qty`, 0))
        ) < 0
        THEN 0
        ELSE (
          SUM(`pending_pa_can_sto_rsto`) - SUM(COALESCE(`txn_qty`, 0))
        )
      END AS qty,
      store_sub_type,
      ROUND(AVG(cogs), 2) AS cogs,
      CASE
        WHEN (
          SUM(`pending_pa_can_sto_rsto_amt`) - SUM(COALESCE(`txn_val`, 0))
        ) < 0
        THEN 0
        ELSE (
          SUM(`pending_pa_can_sto_rsto_amt`) - SUM(COALESCE(`txn_val`, 0))
        )
      END AS amt,
      store_type
    FROM (
      SELECT
        dd.dt AS report_dt,
        c.*
        EXCEPT (city_name, store_type),
        l.store_type,
        CASE
          WHEN l.store_name LIKE '%SS-MH%'
          THEN 'dry'
          WHEN l.store_name = 'GUR-SS_DRY_MH_SILANI _ZL'
          THEN 'dry'
          WHEN l.sub_type = 'SUPERSTORE'
          THEN 'SUPERSTORE'
          WHEN l.store_type = 'RETAIL_STORE'
          THEN 'RETAIL_STORE'
          WHEN l.store_name LIKE '%PHARMA%'
          THEN 'PHARMA_WAREHOUSE'
          WHEN NOT l.store_category IS NULL
          THEN l.store_category
          ELSE l.store_type
        END AS store_sub_type,
        l.city_name,
        t.txn_val,
        t.txn_qty
      FROM gold.ops.shrinkage_raw_pp_against_can AS c
      JOIN dates AS dd
        ON c.to_creation_date >= (
          CASE
            WHEN c.destination_type IN ('RETAIL_STORE')
            THEN DATE_SUB(dd.dt, 30)
            WHEN (
              c.store_name IN ('BLR-DRY-MH-Sumadhura2', 'FBD-DRY-MH')
              AND c.destination_type IN ('WAREHOUSE')
            )
            THEN DATE_SUB(dd.dt, 20)
            WHEN (
              c.store_name IN ('MUM-DRY-MH-SHAKTI') AND c.destination_type IN ('WAREHOUSE')
            )
            THEN DATE_SUB(dd.dt, 30)
            WHEN c.destination_type IN ('WAREHOUSE')
            THEN DATE_SUB(dd.dt, 15)
          END
        )
        AND c.to_creation_date < (
          CASE
            WHEN c.destination_type IN ('RETAIL_STORE')
            THEN DATE_SUB(dd.dt, 29)
            WHEN (
              c.store_name IN ('BLR-DRY-MH-Sumadhura2', 'FBD-DRY-MH')
              AND c.destination_type IN ('WAREHOUSE')
            )
            THEN DATE_SUB(dd.dt, 19)
            WHEN (
              c.store_name IN ('MUM-DRY-MH-SHAKTI') AND c.destination_type IN ('WAREHOUSE')
            )
            THEN DATE_SUB(dd.dt, 29)
            WHEN c.destination_type IN ('WAREHOUSE')
            THEN DATE_SUB(dd.dt, 14)
          END
        )
      LEFT JOIN gold.zepto.store_fact AS l
        ON c.store_name = l.store_name
      LEFT JOIN (
        SELECT
          CAST(datestr AS DATE) AS t_dt,
          store_name,
          sku_id,
          SUM(COALESCE(transaction_qty_cost, 0)) AS txn_val,
          SUM(COALESCE(transaction_qty, 0)) AS txn_qty
        FROM gold.product.shrinkage_txns_closure_tracking AS t
        WHERE
          NOT txn_type IN ('External_PO', 'Customer_RTO_RnR', 'DH_to_Customer')
          AND process_type IN (
            'INPROGRESS_BIN_AGEING_SHRINKAGE',
            'P2D_CANCELLATION_SHRINKAGE',
            'SHRINKAGE_PUTAWAY_INVENTORY',
            'SHRINKAGE'
          )
          AND from_bin IN ('CANCELBIN')
          AND datestr BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
          AND NOT category_name IN ('Zepto Cafe', 'Unlisted1', 'Sample Box')
        GROUP BY ALL
      ) AS t
        ON t.store_name = c.store_name AND LOWER(c.sku) = t.sku_id AND t.t_dt = dd.dt
      WHERE
        (c.txn_closed_on IS NULL OR CAST(c.txn_closed_on AS DATE) >= dd.dt)
        AND c.to_creation_date >= DATE'2026-09-01'
        AND c.to_creation_date < DATE'2026-09-27'
    ) AS `virtual_table`
    GROUP BY ALL
  ) AS a
  LEFT JOIN gold.ops.slp_zone_city_mapping AS b
    ON LOWER(a.city_name) = LOWER(b.City)
  LEFT JOIN gold.ops.sheet_city_targets AS city_sheet
    ON LOWER(a.city_name) = LOWER(city_sheet.City)
  LEFT JOIN gold.ops.sheet_zone_targets AS zone_sheet
    ON LOWER(b.Zone) = LOWER(zone_sheet.Zone)
  LEFT JOIN (
    SELECT DISTINCT
      LOWER(si.product_variant_id) AS pvid,
      si.storage_zone
    FROM gold.zepto.sku_info AS si
  ) AS d
    ON LOWER(a.sku_id) = d.pvid
  WHERE
    NOT EXISTS(
      SELECT
        1
      FROM gold.product.gift_card_skus AS gc
      WHERE
        a.sku_id = gc.gift_sku
    )
    AND a.store <> 'BLR-HSR-Flower-Shop-1'
    AND a.day BETWEEN DATE'2026-10-01' AND DATE'2026-10-11'
  GROUP BY ALL
) AS v
LEFT JOIN VALUES
  ('BLR-27th Main Road','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-BELLANDUR-4','Ashwath S','Ashwath S'),
  ('BLR-Margosa road','Vijay M','Raghavendra Vernekar'),
  ('BLR-Nehru Nagar SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Tippenahalli','Akshay P','Bangareppa CS'),
  ('BLR-GUNJUR Network','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-RAGHAVENDRA LAYOUT NETWORK 2','Suhas N','Raghavendra Vernekar'),
  ('BLR-RICHMOND TOWN SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-RR Nagar Network','Ravishankar Gowda','Deepak D M'),
  ('BLR-TC Palaya','Rizwan Ahmed','Lakshman Balakrishnan'),
  ('BLR-Ullal','Ravishankar Gowda','Deepak D M'),
  ('BLR-JP Nagar Network','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-JP Nagar Network-2','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-Mico Layout Network','Keshav G','Lakshman Balakrishnan'),
  ('MYQ-Bogadi','Santhosha M','Deepak D M'),
  ('PAL-TKV Nagar','Vishnu V','Vishnu V'),
  ('BLR-Electronic City New','Balaji G','Lakshman Balakrishnan'),
  ('BLR-HSR-2','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-BASAVANAPURA SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Banashankari Network','Narasimhamurthy R','Deepak D M'),
  ('BLR-Brookfield Network-2','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-RICHMOND TOWN','Vijay M','Raghavendra Vernekar'),
  ('BLR-Richmond Town Network','Vijay M','Raghavendra Vernekar'),
  ('COI-Sundarapuram','John Britto','John Britto'),
  ('KOC-Kalamassery SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Abbigere','Akshay P','Bangareppa CS'),
  ('BLR-Doddakannelli SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Vidyaranyapura','Akshay P','Bangareppa CS'),
  ('KOC-Thengod','Vishnu V','Vishnu V'),
  ('BLR-Hope Farm New','Ashwath S','Ashwath S'),
  ('BLR-Pipeline road new','Manoj Kj','Bangareppa CS'),
  ('BLR-RAGHAVENDRA LAYOUT','Suhas N','Raghavendra Vernekar'),
  ('BLR-Thyagaraja Nagar','Suhas N','Raghavendra Vernekar'),
  ('KOC-Thrippunithura','Vishnu V','Vishnu V'),
  ('BLR-BROOKEFIELD','Basil Scariya','Lakshman Balakrishnan'),
  ('BLR-Bellandur new','Ashwath S','Ashwath S'),
  ('BLR-Kamakshipalya','Manoj Kj','Bangareppa CS'),
  ('BLR-Marathahalli New','Basil Scariya','Lakshman Balakrishnan'),
  ('BLR-Whitefield Network-2','Basil Scariya','Lakshman Balakrishnan'),
  ('BLR-Kengeri','Ravishankar Gowda','Deepak D M'),
  ('BLR-Peenya New','Akshay P','Bangareppa CS'),
  ('BLR-Ramamurthy Nagar Network','Rizwan Ahmed','Lakshman Balakrishnan'),
  ('BLR-Vijay Nagar Network','Narasimhamurthy R','Deepak D M'),
  ('BLR-CV Raman Nagar Network-2','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-Cholayanakanalli','Akshay P','Bangareppa CS'),
  ('BLR-Electronic City SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Mathikere','Manoj Kj','Bangareppa CS'),
  ('BLR-Doddanekundi','Basil Scariya','Lakshman Balakrishnan'),
  ('BLR-Kasturinagar New','Rizwan Ahmed','Lakshman Balakrishnan'),
  ('BLR-Silicon Town','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Singapura','Akshay P','Bangareppa CS'),
  ('BLR-BTM-2','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-Malleshpalya','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-Magadi Road','Narasimhamurthy R','Deepak D M'),
  ('KOC-Kakkanad','Vishnu V','Vishnu V'),
  ('BLR - Bhadrappa Layout','Mohaideen DH','Ashwath S'),
  ('BLR-Malagala','Narasimhamurthy R','Deepak D M'),
  ('BLR-Narayanapura','Adhavan Subramani','Ashwath S'),
  ('KOC-Kalamassery','Vishnu V','Vishnu V'),
  ('BLR-Seegehalli','Richard Harris','Ashwath S'),
  ('COI-Race Course','John Britto','John Britto'),
  ('BLR-Channasandra','Ashwath S','Ashwath S'),
  ('BLR-JC Nagar','Manoj Kj','Bangareppa CS'),
  ('HBL-Keshwapura','Bangareppa CS','Bangareppa CS'),
  ('BLR-BTM Layout Network-3','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-CV Raman Nagar SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-HEBBAL NEW','Girish N','Ashwath S'),
  ('BLR-Malleshwaram SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Brookfield Network','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-Kalkere','Rizwan Ahmed','Lakshman Balakrishnan'),
  ('BLR-Narayanapura Network','Adhavan Subramani','Ashwath S'),
  ('BLR-Nikoo home SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Teachers colony','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-Banashankari New','Suhas N','Raghavendra Vernekar'),
  ('BLR-Malleshwaram new','Vijay M','Raghavendra Vernekar'),
  ('BLR-SHIVAJI NAGAR Network','Vijay M','Raghavendra Vernekar'),
  ('BLR-Avalahalli Main','Suhas N','Raghavendra Vernekar'),
  ('BLR-BELLANDUR - 2','Ashwath S','Ashwath S'),
  ('BLR-Bellandur SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Bellandur-3','Ashwath S','Ashwath S'),
  ('BLR-RWF Yelahanka','Akshay P','Bangareppa CS'),
  ('HBL-Gokul Road','Bangareppa CS','Bangareppa CS'),
  ('TUM-SS Puram','Akshay P','Bangareppa CS'),
  ('BLR-HSR Layout New','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-JP Nagar SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Singasandra Network','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Bannerghatta SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Manjunatha layout','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-Nikoo Home New','Adhavan Subramani','Ashwath S'),
  ('BLR-Silver County','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-Bagalakunte','Akshay P','Bangareppa CS'),
  ('BLR-Marathahalli-3','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-TMC Layout','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-Banjara Layout','Rizwan Ahmed','Lakshman Balakrishnan'),
  ('BLR-KALYAN NAGAR NEW','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-Kambipura','Ravishankar Gowda','Deepak D M'),
  ('BLR-Peenya SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Vidyaranyapura SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Vijay Nagar SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Kadugodi','Ashwath S','Ashwath S'),
  ('BLR-Mico layout New','Keshav G','Lakshman Balakrishnan'),
  ('BLR-SINGASANDRA','Balaji G','Lakshman Balakrishnan'),
  ('COI-Parashakti nagar','John Britto','John Britto'),
  ('BLR-BTM LAYOUT NEW','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('KOC-Kaloor','Vishnu V','Vishnu V'),
  ('BEL-Sector 12','Majid Kakatikar','Bangareppa CS'),
  ('BLR-Dasarahalli','Mohaideen DH','Ashwath S'),
  ('BLR-RAMAMURTHY NAGAR NEW','Rizwan Ahmed','Lakshman Balakrishnan'),
  ('BLR-GUNJUR','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-Nagavara','Girish N','Ashwath S'),
  ('BLR-Nagondanahalli','Ashwath S','Ashwath S'),
  ('BLR-Sanjaynagar','Akshay P','Bangareppa CS'),
  ('BLR-Sarjapur-2','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-Siddapura','Basil Scariya','Lakshman Balakrishnan'),
  ('BLR-Silver County  SS','Arun Raj','Lakshman Balakrishnan'),
  ('MYQ-Hudco','Santhosha M','Deepak D M'),
  ('BLR-Bannerghatta Network','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-Goraguntepalya','Manoj Kj','Bangareppa CS'),
  ('BLR-BANNERGHATTA','Manjunatha V','Raghavendra Vernekar'),
  ('COI-Peelamedu','John Britto','John Britto'),
  ('BLR-Hegganahalli','Manoj Kj','Bangareppa CS'),
  ('BLR-Peenya Network','Akshay P','Bangareppa CS'),
  ('BEL-Khanapur Road','Majid Kakatikar','Bangareppa CS'),
  ('MYQ-Vani villas','Santhosha M','Deepak D M'),
  ('BLR-Agrahara Road','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-BASAVANAPURA','Richard Harris','Ashwath S'),
  ('BLR-Golahalli','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-Jayanagar 9th block','Suhas N','Raghavendra Vernekar'),
  ('BLR-Junnasandra','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-Yelahanka new town New','Akshay P','Bangareppa CS'),
  ('BLR-Dooravani Nagar','Rizwan Ahmed','Lakshman Balakrishnan'),
  ('BLR-RR Nagar SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Yallapa Garden','Narasimhamurthy R','Deepak D M'),
  ('COI-Vadavalli 1','John Britto','John Britto'),
  ('KOC-Infopark','Vishnu V','Vishnu V'),
  ('MYQ-Kuvempu Nagar','Santhosha M','Deepak D M'),
  ('BLR-Sarjapur New','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-BASAVANAPURA NETWORK 2','Richard Harris','Ashwath S'),
  ('BLR-JP Nagar New','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-Mico layout network-2','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('MYQ-Chamundi Vihar','Santhosha M','Deepak D M'),
  ('BLR-INDIRANAGAR NEW','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Basavanapura Network','Richard Harris','Ashwath S'),
  ('BLR-Gunjur New','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-Neo Town','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Sattava East','Ashwath S','Ashwath S'),
  ('BLR-Shivaji Nagar SS','Arun Raj','Lakshman Balakrishnan'),
  ('KOC-Friendship nagar','Vishnu V','Vishnu V'),
  ('BLR-Michael Palaya','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Nehru Nagar','Akshay P','Bangareppa CS'),
  ('BLR-Yelenahalli','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-Bellandur-5','Ashwath S','Ashwath S'),
  ('BLR-Challakere','Girish N','Ashwath S'),
  ('BLR-Kudlu','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-New Gurappanya Palya','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-Whitefield New','Basil Scariya','Lakshman Balakrishnan'),
  ('MYQ-Vijayanagar','Santhosha M','Deepak D M'),
  ('BLR-BEML Layout','Ravishankar Gowda','Deepak D M'),
  ('BLR-Balagere SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Bommasandra','Balaji G','Lakshman Balakrishnan'),
  ('BLR-HBR Layout','Girish N','Ashwath S'),
  ('BLR-Kumaraswamy Layout','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-Sompura','Sundaresh S','Lakshman Balakrishnan'),
  ('PAL-Pallipuram','Vishnu V','Vishnu V'),
  ('BLR-Bellandur 6','Ashwath S','Ashwath S'),
  ('BLR-JAYANAGAR New','Suhas N','Raghavendra Vernekar'),
  ('BLR-Marathalli SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Choodasandra','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-HSR-3','Saddam Hussain','Lakshman Balakrishnan'),
  ('BLR-Murugeshpalya','Keshav G','Lakshman Balakrishnan'),
  ('HBL-Vidhya Nagar','Bangareppa CS','Bangareppa CS'),
  ('PAL-Kalpathy','Vishnu V','Vishnu V'),
  ('BLR-BHADRAPPA LAYOUT NETWORK','Mohaideen DH','Ashwath S'),
  ('BLR-Belathur','Ashwath S','Ashwath S'),
  ('BLR-Chamrajpet','Narasimhamurthy R','Deepak D M'),
  ('BLR-HSR SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Jakkur Network','Girish N','Ashwath S'),
  ('BLR-Kasavanahalli','Saddam Hussain','Lakshman Balakrishnan'),
  ('COI-Ramnathapuram','John Britto','John Britto'),
  ('COI-Singanallur','John Britto','John Britto'),
  ('BLR-Carmelaram','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-Kannika Nagar','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Marathahalli-4','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-Anjanapura','Suhas N','Raghavendra Vernekar'),
  ('BLR-Electronic City Network-2','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Kothnur New','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR- Brookefield SS','Arun Raj','Lakshman Balakrishnan'),
  ('DEV-MCC','Bangareppa CS','Bangareppa CS'),
  ('KOC-Vallathol Padi','Vishnu V','Vishnu V'),
  ('BLR- Sonnenahalli New','Narasimhamurthy R','Deepak D M'),
  ('BLR-Aswath Nagar','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-Dooravani Nagar SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Garudachar Palya','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-Rajarajeshwari Nagar','Ravishankar Gowda','Deepak D M'),
  ('BLR-Electronic city network','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Nagdevanahalli','Ravishankar Gowda','Deepak D M'),
  ('DEV-Jayanagara','Bangareppa CS','Bangareppa CS'),
  ('BLR-CV RAMAN NAGAR NEW','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-Devasandra Extension','Richard Harris','Ashwath S'),
  ('BLR-Hope Farm SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Kannamangala','Ashwath S','Ashwath S'),
  ('MYQ-Chamrajpura','Santhosha M','Deepak D M'),
  ('BLR-ITPL Layout','Rizwan Ahmed','Lakshman Balakrishnan'),
  ('BLR-Kogilu Road','Adhavan Subramani','Ashwath S'),
  ('BLR-Sunrise Layout','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-Varthur','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-YESHWANTPUR','Manoj Kj','Bangareppa CS'),
  ('COI-R S Puram','John Britto','John Britto'),
  ('BLR-Arekere','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-Yelahanka Network','Akshay P','Bangareppa CS'),
  ('BLR-Jakkur New','Girish N','Ashwath S'),
  ('BLR-RAGHAVENDRA LAYOUT NETWORK','Suhas N','Raghavendra Vernekar'),
  ('KOC-Aluva','Vishnu V','Vishnu V'),
  ('BLR-BTM-3','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-Chandapura','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Doddakannelli','Sundaresh S','Lakshman Balakrishnan'),
  ('COI-Sai baba colony','John Britto','John Britto'),
  ('HOS-Hosur','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Kadarenahalli','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-Kalyan Nagar Network','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-Marathahalli 2','Basil Scariya','Lakshman Balakrishnan'),
  ('BLR-Sattava East SS','Arun Raj','Lakshman Balakrishnan'),
  ('KOC-PALLURTHY','Vishnu V','Vishnu V'),
  ('BLR-Chickpet New','Suhas N','Raghavendra Vernekar'),
  ('BLR-Singasandra SS','Arun Raj','Lakshman Balakrishnan'),
  ('MYQ-Mahadevpura','Santhosha M','Deepak D M'),
  ('BLR-Bagalur','Adhavan Subramani','Ashwath S'),
  ('BLR-Budigere Cross','Ashwath S','Ashwath S'),
  ('BLR-Hennur New','Adhavan Subramani','Ashwath S'),
  ('BLR-Kadarenahalli SS','Arun Raj','Lakshman Balakrishnan'),
  ('BLR-Shivaji nagar New','Vijay M','Raghavendra Vernekar'),
  ('BLR-VIJAY NAGAR','Narasimhamurthy R','Deepak D M'),
  ('BLR-Bannerghatta Network 2','Manjunatha V','Raghavendra Vernekar'),
  ('BLR-CV Raman Nagar Network','Silambarasan E','Lakshman Balakrishnan'),
  ('BLR-Devanahalli','Adhavan Subramani','Ashwath S'),
  ('BLR-Doddathoguru','Balaji G','Lakshman Balakrishnan'),
  ('KOC-Edappally','Vishnu V','Vishnu V'),
  ('MYQ-Rajendra Nagar','Santhosha M','Deepak D M'),
  ('BLR-Kasturinagar','Not Mapped','Not Mapped'),
  ('BLR-SINGASANDRA NEW','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Bidaraguppe','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-Doomasandra','Sundaresh S','Lakshman Balakrishnan'),
  ('KOC-Fort','Vishnu V','Vishnu V'),
  ('BLR-Koramangala Network','Not Mapped','Not Mapped'),
  ('BLR-BTM-2 New','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-Iggalur','Balaji G','Lakshman Balakrishnan'),
  ('BLR-RK Hegde Nagar','Mohaideen DH','Ashwath S'),
  ('BLR-Attibele','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Chikkanagamangala','Balaji G','Lakshman Balakrishnan'),
  ('BLR-Mathikere New','Manoj Kj','Bangareppa CS'),
  ('BLR-Hadosiddapura','Sundaresh S','Lakshman Balakrishnan'),
  ('BLR-Soukya','Ashwath S','Ashwath S'),
  ('BLR-Hennur Main','Adhavan Subramani','Ashwath S'),
  ('BLR-Nelmagala Town','Akshay P','Bangareppa CS'),
  ('HBL-Saptapur','Bangareppa CS','Bangareppa CS'),
  ('BLR-Bommanahalli','Raghavendra Vernekar','Raghavendra Vernekar'),
  ('BLR-Chikkajala','Adhavan Subramani','Ashwath S'),
  ('BLR-Eldorado','Adhavan Subramani','Ashwath S'),
  ('COI-Nehru Nagar','John Britto','John Britto')
  AS m(store_name, clm, leader)
  ON LOWER(TRIM(v.store)) = LOWER(TRIM(m.store_name))
WHERE
  v.zone IN ('South1')
  AND v.store_type IN ('RETAIL_STORE', 'SUPERSTORE')
  AND v.type IN ('Adj', 'FCC', 'PUTAWAY_CLOSURE', 'Proj_PA_ClosureD0', 'RTO_DH', 'RTO_HS', 'Shortpick')
GROUP BY ALL
ORDER BY Date, Leader, CLM, Store, Storage_Zone

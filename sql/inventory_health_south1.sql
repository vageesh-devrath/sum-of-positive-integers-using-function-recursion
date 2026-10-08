WITH store_cte1 /* - store aggregation */ AS (
  SELECT
    'Store' AS agg_level,
    D_minus_1,
    create_date,
    city_name,
    wms_organisation_id,
    sub_store_type,
    planogram_enabled_flag,
    store_name,
    loccode,
    SUM(total_bins_) AS total_bins,
    CASE
      WHEN SUM(audited_bins_mtd) >= SUM(bins_city_calc)
      THEN 1
      ELSE SUM(audited_bins_mtd) / SUM(bins_city_calc)
    END AS city_cc_mtd_per,
    CASE
      WHEN SUM(total_accurate_mtd) >= SUM(audited_bins_mtd)
      THEN 1
      ELSE SUM(total_accurate_mtd) / SUM(audited_bins_mtd)
    END AS city_BA_mtd_per,
    1 - (
      SUM(gross_adj_mtd) / SUM(bookedqty_mtd)
    ) AS city_IA_mtd_per,
    IF(
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) > 1,
      city_BA_mtd_per,
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) * city_BA_mtd_per
    ) AS city_cc_acc_mtd_per,
    CASE
      WHEN planogram_enabled_flag = 'Yes'
      THEN NULL
      ELSE COALESCE((
        SUM(dispersed_skus) / (
          SUM(dispersed_skus) + SUM(ideal_skus)
        )
      ), 0)
    END AS city_dispersion_per,
    CASE
      WHEN planogram_enabled_flag = 'Yes'
      THEN NULL
      ELSE (
        SUM(commingled_bins) / SUM(inventory_bins)
      )
    END AS city_comm_per,
    COALESCE((
      SUM(deviation_qty_DoD) / SUM(putaway_qty_DoD)
    ), 0) AS city_pd_per,
    (
      SUM(accurate_putaway_dod) / SUM(total_putaway_dod)
    ) AS city_PA_acc_per,
    IF(city_dispersion_per <= 0.03, 1, 0.03 / city_dispersion_per) AS disp_health,
    IF(city_comm_per <= 0.03, 1, 0.03 / city_comm_per) AS comm_health,
    1 - city_pd_per AS city_pd_health,
    IF(city_PA_acc_per < 0.95, city_PA_acc_per / 0.95, 1) AS city_pa_acc_health,
    IF(city_BA_mtd_per < 0.95, city_BA_mtd_per / 0.95, 1) AS city_BA_health,
    IF(
      city_cc_mtd_per < (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      city_cc_mtd_per / (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      1
    ) AS city_cc_health,
    (
      city_BA_health * 0.4
    ) + (
      city_pd_health * 0.2
    ) + (
      city_cc_health * 0.4
    ) AS inventory_health,
    MAX(COALESCE(PAT_store_plano, 0)) AS PAT_store_plano_, /* - output health */
    COALESCE(SUM(fcc_orders) / SUM(total_orders), 0) AS FCC,
    COALESCE(SUM(missing_orders) / SUM(total_orders), 0) AS Missing,
    IF(
      SUM(binplaced_hrs) IS NULL,
      SUM(qty_packed) / SUM(packed_hrs),
      SUM(qty_packed) / SUM(binplaced_hrs)
    ) AS IPP,
    IF(PAT_store_plano_ < 0.5, 1, 0.5 / PAT_store_plano_) AS PAT_health,
    IF(FCC < 0.0002, 1, 0.0002 / FCC) AS FCC_health,
    IF(Missing < 0.001, 1, 0.001 / Missing) AS Missing_health,
    IF(IPP > 240, 1, IPP / 240) AS IPP_health,
    (
      PAT_health * 0.3
    ) + (
      FCC_health * 0.25
    ) + (
      Missing_health * 0.15
    ) + (
      IPP_health * 0.3
    ) AS OUTPUT_HEALTH,
    (
      inventory_health + OUTPUT_HEALTH
    ) / 2 AS Net_health,
    0 AS weighted_ih
  FROM gold.ops.dh_inventory_hygiene_db_v2 AS db
  WHERE
    NOT store_id IN (
      '9936fef9-625e-4e24-a4f5-5430942094d3',
      '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
      '6e2a0757-de47-402a-8171-6347999ea68d',
      'f9151779-e612-4196-8799-e16789adb7bb',
      '579ae3b0-5c89-4648-9553-882208515c38',
      '2fc49058-22eb-42c9-9860-9d0ca50712ec',
      '68388560-d036-4e04-8baa-ca9982a1168c',
      '67bd4b56-9ff9-432a-a918-9192a4dd1954',
      'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
      '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
      'e13efdf5-75ac-4dd2-880b-0783b6d36161',
      'c07ed217-8442-40d6-87cc-d39ce00a1051',
      'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
      '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
      '1d752bc7-1802-4e2c-8068-aeabcdacc756'
    )
  GROUP BY
    D_minus_1,
    agg_level,
    create_date,
    city_name,
    wms_organisation_id,
    sub_store_type,
    planogram_enabled_flag,
    store_name,
    loccode
), city_cte1 /* -- city aggregation */ AS (
  SELECT
    'City' AS agg_level,
    D_minus_1,
    create_date,
    city_name,
    wms_organisation_id,
    sub_store_type,
    planogram_enabled_flag,
    '-' AS store_name_,
    '-' AS loccode_,
    SUM(total_bins_) AS total_bins,
    CASE
      WHEN SUM(audited_bins_mtd) >= SUM(bins_city_calc)
      THEN 1
      ELSE SUM(audited_bins_mtd) / SUM(bins_city_calc)
    END AS city_cc_mtd_per,
    CASE
      WHEN SUM(total_accurate_mtd) >= SUM(audited_bins_mtd)
      THEN 1
      ELSE SUM(total_accurate_mtd) / SUM(audited_bins_mtd)
    END AS city_BA_mtd_per,
    1 - (
      SUM(gross_adj_mtd) / SUM(bookedqty_mtd)
    ) AS city_IA_mtd_per,
    IF(
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) > 1,
      city_BA_mtd_per,
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) * city_BA_mtd_per
    ) AS city_cc_acc_mtd_per,
    CASE
      WHEN planogram_enabled_flag = 'Yes'
      THEN NULL
      ELSE COALESCE((
        SUM(dispersed_skus) / (
          SUM(dispersed_skus) + SUM(ideal_skus)
        )
      ), 0)
    END AS city_dispersion_per,
    CASE
      WHEN planogram_enabled_flag = 'Yes'
      THEN NULL
      ELSE (
        SUM(commingled_bins) / SUM(inventory_bins)
      )
    END AS city_comm_per,
    COALESCE((
      SUM(deviation_qty_DoD) / SUM(putaway_qty_DoD)
    ), 0) AS city_pd_per,
    (
      SUM(accurate_putaway_dod) / SUM(total_putaway_dod)
    ) AS city_PA_acc_per,
    IF(city_dispersion_per <= 0.03, 1, 0.03 / city_dispersion_per) AS disp_health,
    IF(city_comm_per <= 0.03, 1, 0.03 / city_comm_per) AS comm_health,
    1 - city_pd_per AS city_pd_health,
    IF(city_PA_acc_per < 0.95, city_PA_acc_per / 0.95, 1) AS city_pa_acc_health,
    IF(city_BA_mtd_per < 0.95, city_BA_mtd_per / 0.95, 1) AS city_BA_health,
    IF(
      city_cc_mtd_per < (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      city_cc_mtd_per / (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      1
    ) AS city_cc_health,
    (
      city_BA_health * 0.4
    ) + (
      city_pd_health * 0.2
    ) + (
      city_cc_health * 0.4
    ) AS inventory_health,
    MAX(COALESCE(PAT_city_plano, 0)) AS PAT_city_plano_, /* - output health */
    COALESCE(SUM(fcc_orders) / SUM(total_orders), 0) AS FCC,
    COALESCE(SUM(missing_orders) / SUM(total_orders), 0) AS Missing,
    IF(
      SUM(binplaced_hrs) IS NULL,
      SUM(qty_packed) / SUM(packed_hrs),
      SUM(qty_packed) / SUM(binplaced_hrs)
    ) AS IPP,
    IF(PAT_city_plano_ < 0.5, 1, 0.5 / PAT_city_plano_) AS PAT_health,
    IF(FCC < 0.0002, 1, 0.0002 / FCC) AS FCC_health,
    IF(Missing < 0.001, 1, 0.001 / Missing) AS Missing_health,
    IF(IPP > 240, 1, IPP / 240) AS IPP_health,
    (
      PAT_health * 0.3
    ) + (
      FCC_health * 0.25
    ) + (
      Missing_health * 0.15
    ) + (
      IPP_health * 0.3
    ) AS OUTPUT_HEALTH,
    (
      inventory_health + OUTPUT_HEALTH
    ) / 2 AS Net_health,
    (
      SUM(total_bins_) / a.city_total_bins
    ) * inventory_health AS weighted_ih
  FROM gold.ops.dh_inventory_hygiene_db_v2 AS db
  LEFT JOIN (
    SELECT
      create_date AS crd,
      city_name AS cty,
      sub_store_type AS sst,
      SUM(total_bins_) AS city_total_bins
    FROM gold.ops.dh_inventory_hygiene_db_v2
    WHERE
      NOT store_id IN (
        '9936fef9-625e-4e24-a4f5-5430942094d3',
        '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
        '6e2a0757-de47-402a-8171-6347999ea68d',
        'f9151779-e612-4196-8799-e16789adb7bb',
        '579ae3b0-5c89-4648-9553-882208515c38',
        '2fc49058-22eb-42c9-9860-9d0ca50712ec',
        '68388560-d036-4e04-8baa-ca9982a1168c',
        '67bd4b56-9ff9-432a-a918-9192a4dd1954',
        'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
        '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
        'e13efdf5-75ac-4dd2-880b-0783b6d36161',
        'c07ed217-8442-40d6-87cc-d39ce00a1051',
        'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
        '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
        '1d752bc7-1802-4e2c-8068-aeabcdacc756'
      )
    GROUP BY
      1,
      2,
      3
  ) AS a
    ON db.create_date = a.crd AND db.city_name = a.cty AND db.sub_store_type = a.sst
  WHERE
    NOT store_id IN (
      '9936fef9-625e-4e24-a4f5-5430942094d3',
      '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
      '6e2a0757-de47-402a-8171-6347999ea68d',
      'f9151779-e612-4196-8799-e16789adb7bb',
      '579ae3b0-5c89-4648-9553-882208515c38',
      '2fc49058-22eb-42c9-9860-9d0ca50712ec',
      '68388560-d036-4e04-8baa-ca9982a1168c',
      '67bd4b56-9ff9-432a-a918-9192a4dd1954',
      'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
      '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
      'e13efdf5-75ac-4dd2-880b-0783b6d36161',
      'c07ed217-8442-40d6-87cc-d39ce00a1051',
      'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
      '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
      '1d752bc7-1802-4e2c-8068-aeabcdacc756'
    )
  GROUP BY
    D_minus_1,
    agg_level,
    create_date,
    city_name,
    wms_organisation_id,
    sub_store_type,
    planogram_enabled_flag,
    a.city_total_bins,
    store_name_,
    loccode_
), city_cte2 AS (
  SELECT
    'City' AS agg_level,
    D_minus_1,
    create_date,
    city_name,
    wms_organisation_id,
    sub_store_type,
    'Total' AS planogram_enabled_flag_,
    '-' AS store_name_,
    '-' AS loccode_,
    SUM(total_bins_) AS total_bins,
    CASE
      WHEN SUM(audited_bins_mtd) >= SUM(bins_city_calc)
      THEN 1
      ELSE SUM(audited_bins_mtd) / SUM(bins_city_calc)
    END AS city_cc_mtd_per,
    CASE
      WHEN SUM(total_accurate_mtd) >= SUM(audited_bins_mtd)
      THEN 1
      ELSE SUM(total_accurate_mtd) / SUM(audited_bins_mtd)
    END AS city_BA_mtd_per,
    1 - (
      SUM(gross_adj_mtd) / SUM(bookedqty_mtd)
    ) AS city_IA_mtd_per,
    IF(
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) > 1,
      city_BA_mtd_per,
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) * city_BA_mtd_per
    ) AS city_cc_acc_mtd_per,
    COALESCE(
      (
        SUM(IF(planogram_enabled_flag = 'Yes', 0, dispersed_skus))
      ) / (
        SUM(IF(planogram_enabled_flag = 'Yes', 0, dispersed_skus)) + SUM(IF(planogram_enabled_flag = 'Yes', 0, ideal_skus))
      ),
      0
    ) AS city_dispersion_per,
    (
      SUM(IF(planogram_enabled_flag = 'Yes', 0, commingled_bins)) / SUM(IF(planogram_enabled_flag = 'Yes', 0, inventory_bins))
    ) AS city_comm_per,
    COALESCE((
      SUM(deviation_qty_DoD) / SUM(putaway_qty_DoD)
    ), 0) AS city_pd_per,
    (
      SUM(accurate_putaway_dod) / SUM(total_putaway_dod)
    ) AS city_PA_acc_per,
    IF(city_dispersion_per <= 0.03, 1, 0.03 / city_dispersion_per) AS disp_health,
    IF(city_comm_per <= 0.03, 1, 0.03 / city_comm_per) AS comm_health,
    1 - city_pd_per AS city_pd_health,
    IF(city_PA_acc_per < 0.95, city_PA_acc_per / 0.95, 1) AS city_pa_acc_health,
    IF(city_BA_mtd_per < 0.95, city_BA_mtd_per / 0.95, 1) AS city_BA_health,
    IF(
      city_cc_mtd_per < (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      city_cc_mtd_per / (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      1
    ) AS city_cc_health,
    a.inv_health,
    MAX(COALESCE(PAT_city, 0)) AS pat_city_, /* - output health */
    COALESCE(SUM(fcc_orders) / SUM(total_orders), 0) AS FCC,
    COALESCE(SUM(missing_orders) / SUM(total_orders), 0) AS Missing,
    IF(
      SUM(binplaced_hrs) IS NULL,
      SUM(qty_packed) / SUM(packed_hrs),
      SUM(qty_packed) / SUM(binplaced_hrs)
    ) AS IPP,
    IF(pat_city_ < 0.5, 1, 0.5 / pat_city_) AS PAT_health,
    IF(FCC < 0.0002, 1, 0.0002 / FCC) AS FCC_health,
    IF(Missing < 0.001, 1, 0.001 / Missing) AS Missing_health,
    IF(IPP > 240, 1, IPP / 240) AS IPP_health,
    (
      PAT_health * 0.3
    ) + (
      FCC_health * 0.25
    ) + (
      Missing_health * 0.15
    ) + (
      IPP_health * 0.3
    ) AS OUTPUT_HEALTH,
    (
      a.inv_health + OUTPUT_HEALTH
    ) / 2 AS Net_health,
    0 AS weighted_ih
  FROM gold.ops.dh_inventory_hygiene_db_v2 AS db
  LEFT JOIN (
    SELECT
      create_date AS crd,
      city_name AS cty,
      sub_store_type AS sst,
      SUM(weighted_ih) AS inv_health
    FROM city_cte1
    GROUP BY
      1,
      2,
      3
  ) AS a
    ON db.create_date = a.crd AND db.city_name = a.cty AND db.sub_store_type = a.sst
  WHERE
    NOT store_id IN (
      '9936fef9-625e-4e24-a4f5-5430942094d3',
      '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
      '6e2a0757-de47-402a-8171-6347999ea68d',
      'f9151779-e612-4196-8799-e16789adb7bb',
      '579ae3b0-5c89-4648-9553-882208515c38',
      '2fc49058-22eb-42c9-9860-9d0ca50712ec',
      '68388560-d036-4e04-8baa-ca9982a1168c',
      '67bd4b56-9ff9-432a-a918-9192a4dd1954',
      'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
      '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
      'e13efdf5-75ac-4dd2-880b-0783b6d36161',
      'c07ed217-8442-40d6-87cc-d39ce00a1051',
      'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
      '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
      '1d752bc7-1802-4e2c-8068-aeabcdacc756'
    )
  GROUP BY
    D_minus_1,
    agg_level,
    create_date,
    city_name,
    wms_organisation_id,
    sub_store_type,
    planogram_enabled_flag_,
    a.inv_health,
    store_name_,
    loccode_
), ent_cte1 /* entity aggregation */ AS (
  SELECT
    'Entity' AS agg_level,
    D_minus_1,
    create_date,
    '-' AS city_name_,
    wms_organisation_id,
    sub_store_type,
    planogram_enabled_flag,
    '-' AS store_name_,
    '-' AS loccode_,
    SUM(total_bins_) AS total_bins,
    CASE
      WHEN SUM(audited_bins_mtd) >= SUM(bins_city_calc)
      THEN 1
      ELSE SUM(audited_bins_mtd) / SUM(bins_city_calc)
    END AS city_cc_mtd_per,
    CASE
      WHEN SUM(total_accurate_mtd) >= SUM(audited_bins_mtd)
      THEN 1
      ELSE SUM(total_accurate_mtd) / SUM(audited_bins_mtd)
    END AS city_BA_mtd_per,
    1 - (
      SUM(gross_adj_mtd) / SUM(bookedqty_mtd)
    ) AS city_IA_mtd_per,
    IF(
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) > 1,
      city_BA_mtd_per,
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) * city_BA_mtd_per
    ) AS city_cc_acc_mtd_per,
    CASE
      WHEN planogram_enabled_flag = 'Yes'
      THEN NULL
      ELSE COALESCE((
        SUM(dispersed_skus) / (
          SUM(dispersed_skus) + SUM(ideal_skus)
        )
      ), 0)
    END AS city_dispersion_per,
    CASE
      WHEN planogram_enabled_flag = 'Yes'
      THEN NULL
      ELSE (
        SUM(commingled_bins) / SUM(inventory_bins)
      )
    END AS city_comm_per,
    COALESCE((
      SUM(deviation_qty_DoD) / SUM(putaway_qty_DoD)
    ), 0) AS city_pd_per,
    (
      SUM(accurate_putaway_dod) / SUM(total_putaway_dod)
    ) AS city_PA_acc_per,
    IF(city_dispersion_per <= 0.03, 1, 0.03 / city_dispersion_per) AS disp_health,
    IF(city_comm_per <= 0.03, 1, 0.03 / city_comm_per) AS comm_health,
    1 - city_pd_per AS city_pd_health,
    IF(city_PA_acc_per < 0.95, city_PA_acc_per / 0.95, 1) AS city_pa_acc_health,
    IF(city_BA_mtd_per < 0.95, city_BA_mtd_per / 0.95, 1) AS city_BA_health,
    IF(
      city_cc_mtd_per < (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      city_cc_mtd_per / (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      1
    ) AS city_cc_health,
    (
      city_BA_health * 0.4
    ) + (
      city_pd_health * 0.2
    ) + (
      city_cc_health * 0.4
    ) AS inventory_health,
    MAX(COALESCE(PAT_entity_plano, 0)) AS PAT_entity_plano_, /* - output health */
    COALESCE(SUM(fcc_orders) / SUM(total_orders), 0) AS FCC,
    COALESCE(SUM(missing_orders) / SUM(total_orders), 0) AS Missing,
    IF(
      SUM(binplaced_hrs) IS NULL,
      SUM(qty_packed) / SUM(packed_hrs),
      SUM(qty_packed) / SUM(binplaced_hrs)
    ) AS IPP,
    IF(PAT_entity_plano_ < 0.5, 1, 0.5 / PAT_entity_plano_) AS PAT_health,
    IF(FCC < 0.0002, 1, 0.0002 / FCC) AS FCC_health,
    IF(Missing < 0.001, 1, 0.001 / Missing) AS Missing_health,
    IF(IPP > 240, 1, IPP / 240) AS IPP_health,
    (
      PAT_health * 0.3
    ) + (
      FCC_health * 0.25
    ) + (
      Missing_health * 0.15
    ) + (
      IPP_health * 0.3
    ) AS OUTPUT_HEALTH,
    (
      inventory_health + OUTPUT_HEALTH
    ) / 2 AS Net_health,
    (
      SUM(total_bins_) / a.entity_total_bins
    ) * inventory_health AS weighted_ih
  FROM gold.ops.dh_inventory_hygiene_db_v2 AS db
  LEFT JOIN (
    SELECT
      create_date AS crd,
      wms_organisation_id AS cty,
      sub_store_type AS sst,
      SUM(total_bins_) AS entity_total_bins
    FROM gold.ops.dh_inventory_hygiene_db_v2
    WHERE
      NOT store_id IN (
        '9936fef9-625e-4e24-a4f5-5430942094d3',
        '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
        '6e2a0757-de47-402a-8171-6347999ea68d',
        'f9151779-e612-4196-8799-e16789adb7bb',
        '579ae3b0-5c89-4648-9553-882208515c38',
        '2fc49058-22eb-42c9-9860-9d0ca50712ec',
        '68388560-d036-4e04-8baa-ca9982a1168c',
        '67bd4b56-9ff9-432a-a918-9192a4dd1954',
        'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
        '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
        'e13efdf5-75ac-4dd2-880b-0783b6d36161',
        'c07ed217-8442-40d6-87cc-d39ce00a1051',
        'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
        '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
        '1d752bc7-1802-4e2c-8068-aeabcdacc756'
      )
    GROUP BY
      1,
      2,
      3
  ) AS a
    ON db.create_date = a.crd
    AND db.wms_organisation_id = a.cty
    AND db.sub_store_type = a.sst
  WHERE
    NOT store_id IN (
      '9936fef9-625e-4e24-a4f5-5430942094d3',
      '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
      '6e2a0757-de47-402a-8171-6347999ea68d',
      'f9151779-e612-4196-8799-e16789adb7bb',
      '579ae3b0-5c89-4648-9553-882208515c38',
      '2fc49058-22eb-42c9-9860-9d0ca50712ec',
      '68388560-d036-4e04-8baa-ca9982a1168c',
      '67bd4b56-9ff9-432a-a918-9192a4dd1954',
      'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
      '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
      'e13efdf5-75ac-4dd2-880b-0783b6d36161',
      'c07ed217-8442-40d6-87cc-d39ce00a1051',
      'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
      '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
      '1d752bc7-1802-4e2c-8068-aeabcdacc756'
    )
  GROUP BY
    D_minus_1,
    agg_level,
    create_date,
    city_name_,
    wms_organisation_id,
    sub_store_type,
    planogram_enabled_flag,
    a.entity_total_bins,
    store_name_,
    loccode_
), ent_cte2 AS (
  SELECT
    'Entity' AS agg_level,
    D_minus_1,
    create_date,
    '-' AS city_name_,
    wms_organisation_id,
    sub_store_type,
    'Total' AS planogram_enabled_flag_,
    '-' AS store_name_,
    '-' AS loccode_,
    SUM(total_bins_) AS total_bins,
    CASE
      WHEN SUM(audited_bins_mtd) >= SUM(bins_city_calc)
      THEN 1
      ELSE SUM(audited_bins_mtd) / SUM(bins_city_calc)
    END AS city_cc_mtd_per,
    CASE
      WHEN SUM(total_accurate_mtd) >= SUM(audited_bins_mtd)
      THEN 1
      ELSE SUM(total_accurate_mtd) / SUM(audited_bins_mtd)
    END AS city_BA_mtd_per,
    1 - (
      SUM(gross_adj_mtd) / SUM(bookedqty_mtd)
    ) AS city_IA_mtd_per,
    IF(
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) > 1,
      city_BA_mtd_per,
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) * city_BA_mtd_per
    ) AS city_cc_acc_mtd_per,
    COALESCE(
      (
        SUM(IF(planogram_enabled_flag = 'Yes', 0, dispersed_skus))
      ) / (
        SUM(IF(planogram_enabled_flag = 'Yes', 0, dispersed_skus)) + SUM(IF(planogram_enabled_flag = 'Yes', 0, ideal_skus))
      ),
      0
    ) AS city_dispersion_per,
    (
      SUM(IF(planogram_enabled_flag = 'Yes', 0, commingled_bins)) / SUM(IF(planogram_enabled_flag = 'Yes', 0, inventory_bins))
    ) AS city_comm_per,
    COALESCE((
      SUM(deviation_qty_DoD) / SUM(putaway_qty_DoD)
    ), 0) AS city_pd_per,
    (
      SUM(accurate_putaway_dod) / SUM(total_putaway_dod)
    ) AS city_PA_acc_per,
    IF(city_dispersion_per <= 0.03, 1, 0.03 / city_dispersion_per) AS disp_health,
    IF(city_comm_per <= 0.03, 1, 0.03 / city_comm_per) AS comm_health,
    1 - city_pd_per AS city_pd_health,
    IF(city_PA_acc_per < 0.95, city_PA_acc_per / 0.95, 1) AS city_pa_acc_health,
    IF(city_BA_mtd_per < 0.95, city_BA_mtd_per / 0.95, 1) AS city_BA_health,
    IF(
      city_cc_mtd_per < (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      city_cc_mtd_per / (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      1
    ) AS city_cc_health,
    a.inv_health,
    MAX(COALESCE(PAT_entity, 0)) AS pat_entity_, /* - output health */
    COALESCE(SUM(fcc_orders) / SUM(total_orders), 0) AS FCC,
    COALESCE(SUM(missing_orders) / SUM(total_orders), 0) AS Missing,
    IF(
      SUM(binplaced_hrs) IS NULL,
      SUM(qty_packed) / SUM(packed_hrs),
      SUM(qty_packed) / SUM(binplaced_hrs)
    ) AS IPP,
    IF(pat_entity_ < 0.5, 1, 0.5 / pat_entity_) AS PAT_health,
    IF(FCC < 0.0002, 1, 0.0002 / FCC) AS FCC_health,
    IF(Missing < 0.001, 1, 0.001 / Missing) AS Missing_health,
    IF(IPP > 240, 1, IPP / 240) AS IPP_health,
    (
      PAT_health * 0.3
    ) + (
      FCC_health * 0.25
    ) + (
      Missing_health * 0.15
    ) + (
      IPP_health * 0.3
    ) AS OUTPUT_HEALTH,
    (
      a.inv_health + OUTPUT_HEALTH
    ) / 2 AS Net_health,
    0 AS weighted_ih
  FROM gold.ops.dh_inventory_hygiene_db_v2 AS db
  LEFT JOIN (
    SELECT
      create_date AS crd,
      wms_organisation_id AS cty,
      sub_store_type AS sst,
      SUM(weighted_ih) AS inv_health
    FROM ent_cte1
    GROUP BY
      1,
      2,
      3
  ) AS a
    ON db.create_date = a.crd
    AND db.wms_organisation_id = a.cty
    AND db.sub_store_type = a.sst
  WHERE
    NOT store_id IN (
      '9936fef9-625e-4e24-a4f5-5430942094d3',
      '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
      '6e2a0757-de47-402a-8171-6347999ea68d',
      'f9151779-e612-4196-8799-e16789adb7bb',
      '579ae3b0-5c89-4648-9553-882208515c38',
      '2fc49058-22eb-42c9-9860-9d0ca50712ec',
      '68388560-d036-4e04-8baa-ca9982a1168c',
      '67bd4b56-9ff9-432a-a918-9192a4dd1954',
      'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
      '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
      'e13efdf5-75ac-4dd2-880b-0783b6d36161',
      'c07ed217-8442-40d6-87cc-d39ce00a1051',
      'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
      '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
      '1d752bc7-1802-4e2c-8068-aeabcdacc756'
    )
  GROUP BY
    D_minus_1,
    agg_level,
    create_date,
    city_name_,
    wms_organisation_id,
    sub_store_type,
    planogram_enabled_flag_,
    a.inv_health,
    store_name_,
    loccode_
), pindia_cte1 /* pan india */ AS (
  SELECT
    'Pan_india' AS agg_level,
    D_minus_1,
    create_date,
    '-' AS city_name_,
    '-' AS wms_organisation_id_,
    sub_store_type,
    planogram_enabled_flag,
    '-' AS store_name_,
    '-' AS loccode_,
    SUM(total_bins_) AS total_bins,
    CASE
      WHEN SUM(audited_bins_mtd) >= SUM(bins_city_calc)
      THEN 1
      ELSE SUM(audited_bins_mtd) / SUM(bins_city_calc)
    END AS city_cc_mtd_per,
    CASE
      WHEN SUM(total_accurate_mtd) >= SUM(audited_bins_mtd)
      THEN 1
      ELSE SUM(total_accurate_mtd) / SUM(audited_bins_mtd)
    END AS city_BA_mtd_per,
    1 - (
      SUM(gross_adj_mtd) / SUM(bookedqty_mtd)
    ) AS city_IA_mtd_per,
    IF(
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) > 1,
      city_BA_mtd_per,
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) * city_BA_mtd_per
    ) AS city_cc_acc_mtd_per,
    CASE
      WHEN planogram_enabled_flag = 'Yes'
      THEN NULL
      ELSE COALESCE((
        SUM(dispersed_skus) / (
          SUM(dispersed_skus) + SUM(ideal_skus)
        )
      ), 0)
    END AS city_dispersion_per,
    CASE
      WHEN planogram_enabled_flag = 'Yes'
      THEN NULL
      ELSE (
        SUM(commingled_bins) / SUM(inventory_bins)
      )
    END AS city_comm_per,
    COALESCE((
      SUM(deviation_qty_DoD) / SUM(putaway_qty_DoD)
    ), 0) AS city_pd_per,
    (
      SUM(accurate_putaway_dod) / SUM(total_putaway_dod)
    ) AS city_PA_acc_per,
    IF(city_dispersion_per <= 0.03, 1, 0.03 / city_dispersion_per) AS disp_health,
    IF(city_comm_per <= 0.03, 1, 0.03 / city_comm_per) AS comm_health,
    1 - city_pd_per AS city_pd_health,
    IF(city_PA_acc_per < 0.95, city_PA_acc_per / 0.95, 1) AS city_pa_acc_health,
    IF(city_BA_mtd_per < 0.95, city_BA_mtd_per / 0.95, 1) AS city_BA_health,
    IF(
      city_cc_mtd_per < (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      city_cc_mtd_per / (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      1
    ) AS city_cc_health,
    (
      city_BA_health * 0.4
    ) + (
      city_pd_health * 0.2
    ) + (
      city_cc_health * 0.4
    ) AS inventory_health,
    MAX(COALESCE(PAT_india_plano, 0)) AS PAT_india_plano_, /* - output health */
    COALESCE(SUM(fcc_orders) / SUM(total_orders), 0) AS FCC,
    COALESCE(SUM(missing_orders) / SUM(total_orders), 0) AS Missing,
    IF(
      SUM(binplaced_hrs) IS NULL,
      SUM(qty_packed) / SUM(packed_hrs),
      SUM(qty_packed) / SUM(binplaced_hrs)
    ) AS IPP,
    IF(PAT_india_plano_ < 0.5, 1, 0.5 / PAT_india_plano_) AS PAT_health,
    IF(FCC < 0.0002, 1, 0.0002 / FCC) AS FCC_health,
    IF(Missing < 0.001, 1, 0.001 / Missing) AS Missing_health,
    IF(IPP > 240, 1, IPP / 240) AS IPP_health,
    (
      PAT_health * 0.3
    ) + (
      FCC_health * 0.25
    ) + (
      Missing_health * 0.15
    ) + (
      IPP_health * 0.3
    ) AS OUTPUT_HEALTH,
    (
      inventory_health + OUTPUT_HEALTH
    ) / 2 AS Net_health,
    (
      SUM(total_bins_) / a.india_total_bins
    ) * inventory_health AS weighted_ih
  FROM gold.ops.dh_inventory_hygiene_db_v2 AS db
  LEFT JOIN (
    SELECT
      create_date AS crd,
      sub_store_type AS sst,
      SUM(total_bins_) AS india_total_bins
    FROM gold.ops.dh_inventory_hygiene_db_v2
    WHERE
      NOT store_id IN (
        '9936fef9-625e-4e24-a4f5-5430942094d3',
        '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
        '6e2a0757-de47-402a-8171-6347999ea68d',
        'f9151779-e612-4196-8799-e16789adb7bb',
        '579ae3b0-5c89-4648-9553-882208515c38',
        '2fc49058-22eb-42c9-9860-9d0ca50712ec',
        '68388560-d036-4e04-8baa-ca9982a1168c',
        '67bd4b56-9ff9-432a-a918-9192a4dd1954',
        'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
        '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
        'e13efdf5-75ac-4dd2-880b-0783b6d36161',
        'c07ed217-8442-40d6-87cc-d39ce00a1051',
        'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
        '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
        '1d752bc7-1802-4e2c-8068-aeabcdacc756'
      )
    GROUP BY
      1,
      2
  ) AS a
    ON db.create_date = a.crd AND db.sub_store_type = a.sst
  WHERE
    NOT store_id IN (
      '9936fef9-625e-4e24-a4f5-5430942094d3',
      '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
      '6e2a0757-de47-402a-8171-6347999ea68d',
      'f9151779-e612-4196-8799-e16789adb7bb',
      '579ae3b0-5c89-4648-9553-882208515c38',
      '2fc49058-22eb-42c9-9860-9d0ca50712ec',
      '68388560-d036-4e04-8baa-ca9982a1168c',
      '67bd4b56-9ff9-432a-a918-9192a4dd1954',
      'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
      '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
      'e13efdf5-75ac-4dd2-880b-0783b6d36161',
      'c07ed217-8442-40d6-87cc-d39ce00a1051',
      'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
      '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
      '1d752bc7-1802-4e2c-8068-aeabcdacc756'
    )
  GROUP BY
    D_minus_1,
    agg_level,
    create_date,
    city_name_,
    wms_organisation_id_,
    sub_store_type,
    planogram_enabled_flag,
    a.india_total_bins,
    store_name_,
    loccode_
), pindia_cte2 AS (
  SELECT
    'Pan_india' AS agg_level,
    D_minus_1,
    create_date,
    '-' AS city_name_,
    '-' AS wms_organisation_id_,
    sub_store_type,
    'Total' AS planogram_enabled_flag_,
    '-' AS store_name_,
    '-' AS loccode_,
    SUM(total_bins_) AS total_bins,
    CASE
      WHEN SUM(audited_bins_mtd) >= SUM(bins_city_calc)
      THEN 1
      ELSE SUM(audited_bins_mtd) / SUM(bins_city_calc)
    END AS city_cc_mtd_per,
    CASE
      WHEN SUM(total_accurate_mtd) >= SUM(audited_bins_mtd)
      THEN 1
      ELSE SUM(total_accurate_mtd) / SUM(audited_bins_mtd)
    END AS city_BA_mtd_per,
    1 - (
      SUM(gross_adj_mtd) / SUM(bookedqty_mtd)
    ) AS city_IA_mtd_per,
    IF(
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) > 1,
      city_BA_mtd_per,
      (
        SUM(audited_bins_mtd) / SUM(target_mtd_)
      ) * city_BA_mtd_per
    ) AS city_cc_acc_mtd_per,
    COALESCE(
      (
        SUM(IF(planogram_enabled_flag = 'Yes', 0, dispersed_skus))
      ) / (
        SUM(IF(planogram_enabled_flag = 'Yes', 0, dispersed_skus)) + SUM(IF(planogram_enabled_flag = 'Yes', 0, ideal_skus))
      ),
      0
    ) AS city_dispersion_per,
    (
      SUM(IF(planogram_enabled_flag = 'Yes', 0, commingled_bins)) / SUM(IF(planogram_enabled_flag = 'Yes', 0, inventory_bins))
    ) AS city_comm_per,
    COALESCE((
      SUM(deviation_qty_DoD) / SUM(putaway_qty_DoD)
    ), 0) AS city_pd_per,
    (
      SUM(accurate_putaway_dod) / SUM(total_putaway_dod)
    ) AS city_PA_acc_per,
    IF(city_dispersion_per <= 0.03, 1, 0.03 / city_dispersion_per) AS disp_health,
    IF(city_comm_per <= 0.03, 1, 0.03 / city_comm_per) AS comm_health,
    1 - city_pd_per AS city_pd_health,
    IF(city_PA_acc_per < 0.95, city_PA_acc_per / 0.95, 1) AS city_pa_acc_health,
    IF(city_BA_mtd_per < 0.95, city_BA_mtd_per / 0.95, 1) AS city_BA_health,
    IF(
      city_cc_mtd_per < (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      city_cc_mtd_per / (
        SUM(target_mtd_) / SUM(total_bins_)
      ),
      1
    ) AS city_cc_health,
    a.inv_health,
    MAX(COALESCE(PAT_india, 0)) AS PAT_india_, /* - output health */
    COALESCE(SUM(fcc_orders) / SUM(total_orders), 0) AS FCC,
    COALESCE(SUM(missing_orders) / SUM(total_orders), 0) AS Missing,
    IF(
      SUM(binplaced_hrs) IS NULL,
      SUM(qty_packed) / SUM(packed_hrs),
      SUM(qty_packed) / SUM(binplaced_hrs)
    ) AS IPP,
    IF(PAT_india_ < 0.5, 1, 0.5 / PAT_india_) AS PAT_health,
    IF(FCC < 0.0002, 1, 0.0002 / FCC) AS FCC_health,
    IF(Missing < 0.001, 1, 0.001 / Missing) AS Missing_health,
    IF(IPP > 240, 1, IPP / 240) AS IPP_health,
    (
      PAT_health * 0.3
    ) + (
      FCC_health * 0.25
    ) + (
      Missing_health * 0.15
    ) + (
      IPP_health * 0.3
    ) AS OUTPUT_HEALTH,
    (
      a.inv_health + OUTPUT_HEALTH
    ) / 2 AS Net_health,
    0 AS weighted_ih
  FROM gold.ops.dh_inventory_hygiene_db_v2 AS db
  LEFT JOIN (
    SELECT
      create_date AS crd,
      sub_store_type AS sst,
      SUM(weighted_ih) AS inv_health
    FROM pindia_cte1
    GROUP BY
      1,
      2
  ) AS a
    ON db.create_date = a.crd AND db.sub_store_type = a.sst
  WHERE
    NOT store_id IN (
      '9936fef9-625e-4e24-a4f5-5430942094d3',
      '00c35027-e894-41d8-a1dc-4c4ce4e5cad4',
      '6e2a0757-de47-402a-8171-6347999ea68d',
      'f9151779-e612-4196-8799-e16789adb7bb',
      '579ae3b0-5c89-4648-9553-882208515c38',
      '2fc49058-22eb-42c9-9860-9d0ca50712ec',
      '68388560-d036-4e04-8baa-ca9982a1168c',
      '67bd4b56-9ff9-432a-a918-9192a4dd1954',
      'ec219202-e2cb-4726-b5e6-d0e6fc6025db',
      '7d28cb90-cc78-4d24-a284-c01527b2fbbd',
      'e13efdf5-75ac-4dd2-880b-0783b6d36161',
      'c07ed217-8442-40d6-87cc-d39ce00a1051',
      'a2ee7763-c871-4b5e-ab33-fbc48e923b7b',
      '0a357d97-30cb-4eb4-a4b8-0e1fba2471d8',
      '1d752bc7-1802-4e2c-8068-aeabcdacc756'
    )
  GROUP BY
    D_minus_1,
    agg_level,
    create_date,
    city_name_,
    wms_organisation_id_,
    sub_store_type,
    planogram_enabled_flag_,
    a.inv_health,
    store_name_,
    loccode_
), latest_employee_site AS (
  SELECT
    es.*,
    ROW_NUMBER() OVER (PARTITION BY es.employee_id ORDER BY es.updated_on DESC) AS rn
  FROM silver.hrms.employee_site AS es
  WHERE
    es.type = 'PRIMARY'
), cc_associate AS (
  SELECT DISTINCT
    s1.name AS employee_primary_site,
    COUNT(DISTINCT e1.code) AS cc_count
  FROM silver.hrms.employee AS e1
  LEFT JOIN silver.hrms.user AS u1
    ON e1.user_id = u1.id
  LEFT JOIN silver.hrms.role AS r1
    ON u1.role_id = r1.id
  LEFT JOIN latest_employee_site AS es1
    ON e1.id = es1.employee_id AND es1.type = 'PRIMARY'
  LEFT JOIN silver.hrms.site AS s1
    ON es1.site_id = s1.id
  LEFT JOIN silver.hrms.city AS c1
    ON s1.city_id = c1.id
  LEFT JOIN silver.hrms.site_category AS sc1
    ON s1.category = sc1.id
  LEFT JOIN silver.hrms.vendor_org AS vo
    ON vo.id = e1.workforce_vendor_org_id
  WHERE
    u1.status IN ('ACTIVE')
    AND UPPER(r1.team) IN ('DH', 'CAFE', 'SUPERSTORE')
    AND r1.name ILIKE '%cc%'
    AND NOT r1.name IN (
      'Flex',
      'FLEX_CITY',
      'Admin - DH',
      'Associate Engagement Lead',
      'Associate Engagement Lead JSW',
      'Associate Engagement Specialist',
      'Associate Experience Lead',
      'Associate Experience Specialist',
      'City L&D Manager',
      'DH_Central HR',
      'DH_City HR',
      'DH_City_Head',
      'DH_City_Head Hybrid',
      'DH_CLM Hybrid',
      'DH_DCLM',
      'DH_DDHM',
      'DH_DDHM Hybrid',
      'DH_Deputy DHM',
      'DH_Deputy RCLM',
      'DH_DHM Hybrid',
      'DH_Field Recruiter',
      'DH_Hiring Champion',
      'DH_HR Recruiter',
      'DH_Onboarding Executive',
      'DH_OT Approver',
      'DH_Planogram Manager',
      'DH_RCLM Hybrid',
      'DH_Regional HR Manager',
      'DH_Rider Shift Incharge',
      'DH_Rider Shift Incharge_NAPS',
      'DH_Shift Incharge',
      'DH_Shift Incharge_N',
      'DH_Shift Incharge_NAPS',
      'DH_Shift Incharge_NATS',
      'DH_Site HR',
      'DH_SR SHIFT INCHARGE',
      'DH_STEP UP - STORE SHIFT INCHARGE',
      'DH_Store Captain_LM',
      'DH_ZBM',
      'FM_Facility Manager',
      'FM_Multi Skilled Technician',
      'FM_Telecaller',
      'FR_Loss Prevention Associate',
      'Freelancer_Referral',
      'L&D_Manager',
      'Payroll Executive',
      'Regional ER/IR Manager',
      'SIS - Director',
      'SIS-DSM NEW',
      'SIS-EDGE naps',
      'SIS-EDGE1',
      'SIS-Packer',
      'SIS-RSI',
      'Super Admin - DH',
      'Test-Packer',
      'Vendor_Refferal'
    )
    AND e1.status IN ('ONBOARDING_INITIATED', 'ONBOARDING_COMPLETED')
  GROUP BY ALL
)
SELECT
  DATE_TRUNC('DAY', `create_date`) AS `create_date`,
  `store_name` AS `store_name`,
  `sub_store_type` AS `sub_store_type`,
  `planogram_enabled_flag` AS `planogram_enabled_flag`,
  `city_name` AS `city_name`,
  SUM(`total_bins`) AS `Total Bins`,
  SUM(`city_cc_mtd_per`) AS `CC MTD %`,
  SUM(`city_BA_mtd_per`) AS `BA MTD %`,
  SUM(`city_IA_mtd_per`) AS `IA MTD %`,
  SUM(`city_cc_acc_mtd_per`) AS `CC ACC %`,
  SUM(`city_pd_per`) AS `PD %`,
  SUM(`inventory_health`) AS `Inv Health `,
  SUM(`PAT_store_plano_`) AS `PAT`,
  SUM(`FCC`) AS `FCC`,
  SUM(`Missing`) AS `MISSING`,
  SUM(`IPP`) AS `IPP`,
  SUM(`OUTPUT_HEALTH`) AS `Output Health`,
  SUM(`Net_health`) AS `Net Health`,
  SUM(`cc_count`) AS `cc associate count`
FROM (
  SELECT
    a.*,
    cca.cc_count
  FROM (
    SELECT
      *,
      CAST(d_minus_1 - create_date AS INT) AS Report
    FROM store_cte1
    UNION ALL
    SELECT
      *,
      CAST(d_minus_1 - create_date AS INT) AS Report
    FROM city_cte1
    UNION ALL
    SELECT
      *,
      CAST(d_minus_1 - create_date AS INT) AS Report
    FROM city_cte2
    UNION ALL
    SELECT
      *,
      CAST(d_minus_1 - create_date AS INT) AS Report
    FROM ent_cte1
    UNION ALL
    SELECT
      *,
      CAST(d_minus_1 - create_date AS INT) AS Report
    FROM ent_cte2
    UNION ALL
    SELECT
      *,
      CAST(d_minus_1 - create_date AS INT) AS Report
    FROM pindia_cte1
    UNION ALL
    SELECT
      *,
      CAST(d_minus_1 - create_date AS INT) AS Report
    FROM pindia_cte2
  ) AS a
  LEFT JOIN cc_associate AS cca
    ON cca.employee_primary_site = a.store_name
) AS `virtual_table`
WHERE
  `Report` IN (0)
  AND agg_level IN ('Store')
  AND city_name IN (
    'Belgavi', 'Bengaluru', 'Coimbatore', 'Davanagere', 'Hosur',
    'Hubballi', 'Kochi', 'Mysuru', 'Palakkad', 'Tumkuru'
  )
GROUP BY
  DATE_TRUNC('DAY', `create_date`),
  `store_name`,
  `sub_store_type`,
  `planogram_enabled_flag`,
  `city_name`
ORDER BY
  city_name,
  create_date DESC

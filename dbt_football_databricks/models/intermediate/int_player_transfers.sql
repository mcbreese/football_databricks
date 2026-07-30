{{ config(
    materialized='incremental',
    unique_key='player_transfer_sk',
    on_schema_change='sync_all_columns'
) }}
    -- Tell dbt to build this as an incremental table (uses MERGE INTO in Snowflake)
    -- Primary key used to match existing records for UPSERTs (updates matching rows, inserts new ones)
    -- Automatically add or update schema columns in the target table if model columns change

WITH transfers AS (

    SELECT
        -- Primary Surrogate Key (generated in Staging via dbt_utils.generate_surrogate_key)
        tr.player_transfer_sk,
        
        -- Transfer Details & Business Facts
        tr.transfer_date,
        tr.transfer_season,
        tr.transfer_fee,
        tr.market_value_in_eur,

        -- Foreign Keys (used for joins downstream)
        tr.player_id,
        tr.from_club_id,
        tr.to_club_id,

        -- Audit Metadata
        tr.loaded_timestamp AS transfer_loaded_timestamp,
        tr.source_file AS transfer_source_file

    FROM {{ ref('stg_transfers') }} AS tr

    /* 
      During incremental runs, this block filters the source table to ONLY process 
      transfers loaded after the latest timestamp currently in the target table.
      During a --full-refresh, dbt ignores this block completely.
    */
    {% if is_incremental() %}
    -- `{{ this }}` refers to the target table ALREADY IN THE WAREHOUSE
    -- This query finds the latest timestamp currently stored in production
      WHERE tr.loaded_timestamp > (SELECT MAX(transfer_loaded_timestamp) FROM {{ this }})
    {% endif %}

),

joined AS (

    SELECT
        -- Primary Key
        tr.player_transfer_sk,
        
        -- Enriched Club Names
        from_club.name AS from_club_name,
        to_club.name AS to_club_name,

        -- Transfer Facts
        tr.transfer_date,
        tr.transfer_season,
        tr.transfer_fee,
        tr.market_value_in_eur,

        -- Enriched Player Attributes
        pl.player_name,
        pl.nationality,
        pl.position,
        pl.sub_position,
        pl.foot,
        pl.height_in_cm,
        pl.date_of_birth,
        pl.age_in_years,
        pl.last_season,

        -- Foreign Keys
        tr.player_id,
        tr.from_club_id,
        tr.to_club_id,

        -- Target Metadata (retaining transfer table timestamp for downstream incremental tracking)
        tr.transfer_loaded_timestamp,
        tr.transfer_source_file

    FROM transfers AS tr
    
    -- Join to get player metadata (joins against current stg_players view)
    LEFT JOIN {{ ref('stg_players') }} AS pl
        ON tr.player_id = pl.player_id
        
    -- Join to get selling club name
    LEFT JOIN {{ ref('stg_clubs') }} AS from_club
        ON tr.from_club_id = from_club.club_id
        
    -- Join to get buying club name
    LEFT JOIN {{ ref('stg_clubs') }} AS to_club
        ON tr.to_club_id = to_club.club_id
)

SELECT * 
FROM joined
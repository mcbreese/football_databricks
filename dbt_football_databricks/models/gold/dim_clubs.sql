{{ config(
    materialized='table'
) }}


SELECT club_id
    , name
    , loaded_timestamp
FROM {{ ref('int_clubs') }} AS cl

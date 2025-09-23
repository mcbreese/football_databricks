WITH source
AS (
	select * from {{ source('football_stg', 'stg_transfers') }}
	)

SELECT *
FROM source
-- Refer to macro in macros folder
{{ materialization_config() }}

WITH source
AS (
	select * from {{ source('football_raw', 'raw_appearances') }}
	)
	,appearances
AS (
	SELECT
		-- primary key
		-- we are using a combination of columns to make a unique key, this is a great way to handle source tables without a natural primary key
		{{ dbt_utils.generate_surrogate_key(['appearance_id', 'game_id', 'player_id']) }} as appearance_player_sk,
		-- foreign keys
		appearance_id
		,game_id
		,player_id
		,ISNULL(player_club_id,0) AS player_club_id
		,competition_id
		,
		-- dimensions
		player_name
		,DATE AS appearance_date
		-- facts
		,yellow_cards
		,red_cards
		,goals
		,assists
		,minutes_played
		-- metadata
		,loaded_timestamp
		,source_file
	FROM source
	)
SELECT *
FROM appearances
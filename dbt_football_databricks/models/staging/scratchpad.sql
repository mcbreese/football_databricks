with source as (

    select * from `learning_catalog`.`football_raw`.`raw_games`

),

games as (

    select
        -- primary key
        -- game_id is the natural primary key for this table
        md5(cast(concat(coalesce(cast(game_id as string), '_dbt_utils_surrogate_key_null_')) as string)) as game_sk,
        game_id,

        -- foreign keys
        competition_id,
        home_club_id,
        away_club_id,

        -- dimensions
        season,
        -- Cast the date to ensure it is in the correct format
        cast(date as date) as game_date,
        home_club_goals,
        away_club_goals,

        -- metadata
        loaded_timestamp,
        source_file

    from source

)

select * from games
limit 10;
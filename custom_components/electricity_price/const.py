DOMAIN = "electricity_price"
NAME = "total_electricity_price"
ENTITY_ID = "sensor.total_electricity_price"

CONF_TAX = "tax"
CONF_CHARGE = "charge"
CONF_FEE_HIGH = "fee_high"
CONF_FEE_MEDIUM = "fee_medium"
CONF_FEE_LOW = "fee_low"
CONF_FEE_HIGH_START_DATE = "fee_high_start_date"
CONF_FEE_HIGH_END_DATE = "fee_high_end_date"
CONF_FEE_MEDIUM_START_DATE = "fee_medium_start_date"
CONF_FEE_MEDIUM_END_DATE = "fee_medium_end_date"
CONF_FEE_LOW_START_DATE = "fee_low_start_date"
CONF_FEE_LOW_END_DATE = "fee_low_end_date"
CONF_FEE_HIGH_START_TIME = "fee_high_start_time"
CONF_FEE_MEDIUM_START_TIME = "fee_medium_start_time"
CONF_FEE_LOW_START_TIME = "fee_low_start_time"

CONF_TRANSPORT_FEE = "transport_fee"
CONF_HIGH_FEE_PERIOD = "high_fee_period"
CONF_LOW_FEE_PERIOD = "high_fee_period"
CONF_LOW_LOAD_TIMES = "low_load_times"
CONF_HIGH_LOAD_TIMES = "high_load_times"
CONF_PEAK_LOAD_TIMES = "peak_load_times"
CONF_START_DATE = "start_date"
CONF_END_DATE = "end_date"
CONF_START_TIME = "start_time"
CONF_END_TIME = "end_time"

CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD = "transport_fee_low_dates_low_load"
CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD = "transport_fee_low_dates_high_load"
CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD = "transport_fee_low_dates_peak_load"
CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD = "transport_fee_low_dates_low_load"
CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD = "transport_fee_low_dates_high_load"
CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD = "transport_fee_low_dates_peak_load"
CONF_HIGH_FEE_DATES = "high_fee_dates"
CONF_LOW_FEE_DATES = "high_fee_dates"
CONF_LOW_LOAD_TIMES = "low_load_times"
CONF_HIGH_LOAD_TIMES = "high_load_times"
CONF_PEAK_LOAD_TIMES = "peak_load_times"
CONF_TRANSPORT_LOW = "transport_low"
CONF_TRANSPORT_HIGH = "transport_high"
CONF_TRANSPORT_PEAK = "transport_peak"

CONF_ELOVERBLIK_TOKEN = "eloverblik_token"
CONF_METERING_POINT = "metering_point"
CONF_PRICE_SENSOR = "price_sensor"

ATTR_TODAY = "today"
ATTR_TOMORROW = "tomorrow"
ATTR_TOTAL_TODAY = "prices_today"
ATTR_TOTAL_TOMORROW = "prices_tomorrow"
ATTR_CURRENCY = "currency"
ATTR_COUNTRY = "country"
ATTR_REGION = "region"
ATTR_CURRENT_PRICE = "current_price"
ATTR_CURRENT_RAW_PRICE = "current_raw_price"
ATTR_CURRENT_TRANSPORT_FEES = "current_transport_fees"
ATTR_CURRENT_TAX = "current_tax"
ATTR_CURRENT_ELECTRICITY_FEE = "current_electricity_fee"
ATTR_STATE_CLASS = "state_class"
ATTR_LAST_UPDATED = "last_updated"
ATTR_ALL_TARIFS = "tarifs"
ATTR_TRANS_NETTARIF = "transmissions_nettarif"
ATTR_SYSTEMTARIF = "systemtarif"
ATTR_ELAFGIFT = "elafgift"
ATTR_HOUR_NETTARIF = "nettarif_c_time"

CONF_DEFAULT_TARIFS = {
    ATTR_TRANS_NETTARIF: 0.058,
    ATTR_SYSTEMTARIF: 0.054,
    ATTR_ELAFGIFT: 0.008,
    "January": [
        0.1701, 0.1701, 0.1701, 0.1701, 0.1701, 0.1701, 0.5103, 0.5103, 0.5103, 0.5103, 0.5103, 0.5103,
        0.5103, 0.5103, 0.5103, 0.5103, 0.5103, 1.5308, 1.5308, 1.5308, 1.5308, 0.5103, 0.5103, 0.5103
    ],
    "February": [
        0.1837, 0.1837, 0.1837, 0.1837, 0.1837, 0.1837, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511,
        0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 1.6533, 1.6533, 1.6533, 1.6533, 0.5511, 0.5511, 0.5511
    ],
    "March": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528,
        0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 1.3584, 1.3584, 1.3584, 1.3584, 0.4528, 0.4528, 0.4528
    ],
    "April": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264,
        0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.5887, 0.5887, 0.5887, 0.5887, 0.2264, 0.2264, 0.2264
    ],
    "May": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264,
        0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.5887, 0.5887, 0.5887, 0.5887, 0.2264, 0.2264, 0.2264
    ],
    "June": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264,
        0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.5887, 0.5887, 0.5887, 0.5887, 0.2264, 0.2264, 0.2264
    ],
    "July": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264,
        0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.5887, 0.5887, 0.5887, 0.5887, 0.2264, 0.2264, 0.2264
    ],
    "August": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264,
        0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.5887, 0.5887, 0.5887, 0.5887, 0.2264, 0.2264, 0.2264
    ],
    "September": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264,
        0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.5887, 0.5887, 0.5887, 0.5887, 0.2264, 0.2264, 0.2264
    ],
    "October": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528,
        0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 1.3584, 1.3584, 1.3584, 1.3584, 0.4528, 0.4528, 0.4528
    ],
    "November": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528,
        0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 1.3584, 1.3584, 1.3584, 1.3584, 0.4528, 0.4528, 0.4528
    ],
    "December": [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528,
        0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 1.3584, 1.3584, 1.3584, 1.3584, 0.4528, 0.4528, 0.4528
    ]
}

CONF_DEFAULT_SUMMER_TARIFS = {
    ATTR_TRANS_NETTARIF: 0.058,
    ATTR_SYSTEMTARIF: 0.054,
    ATTR_ELAFGIFT: 0.008,
    ATTR_HOUR_NETTARIF: [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.2264,
        0.2264, 0.2264, 0.2264, 0.2264, 0.2264, 0.5887, 0.5887, 0.5887, 0.5887, 0.2264, 0.2264, 0.2264
    ]
}
CONF_DEFAULT_WINTER_TARIFS = {
    ATTR_TRANS_NETTARIF: 0.058,
    ATTR_SYSTEMTARIF: 0.054,
    ATTR_ELAFGIFT: 0.008,
    ATTR_HOUR_NETTARIF: [
        0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.1509, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 0.4528,
        0.4528, 0.4528, 0.4528, 0.4528, 0.4528, 1.3584, 1.3584, 1.3584, 1.3584, 0.4528, 0.4528, 0.4528
    ]
}

CONST_HOURS = [
    "00",
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23"
]
CONST_MONTHS = {
    "01": ["january", "jan", 1],
    "02": ["february", "feb", 2],
    "03": ["march", "mar", 3],
    "04": ["april", "apr", 4],
    "05": ["may", "may", 5],
    "06": ["june", "jun", 6],
    "07": ["july", "jul", 7],
    "08": ["august", "aug", 8],
    "09": ["september", "sep", 9],
    "10": ["october", "oct", 10],
    "11": ["november", "nov", 11],
    "12": ["december", "dec", 11],
}

# https://radiuselnet.dk/elnetkunder/tariffer-og-netabonnement/
# https://andelenergi.dk/kundeservice/aftaler-og-priser/nye-tariffer-for-el/ <- here, jan, feb, and march are different
CONST_DEFAULT_FEES = {
    "high_date_low_load": 17.01,
    "high_date_high_load": 51.03,
    "high_date_peak_load": 153.08,
    "low_date_low_load": 17.01,
    "low_date_high_load": 25.51,
    "low_date_peak_load": 66.33,
}


MOCK_TEAM_CONTEXT = {
    "team_name": "UW Orbital",
    "repo_url": "https://github.com/UWOrbital/satellite",
    "subsystems": [
        "Ground Station Communication",
        "Attitude Determination and Control",
        "Power Systems",
        "On-Board Data Handling",
        "Payload Imaging"
    ],
    "blockers": [
        "Lacks geospatial mapping tooling for ground station coverage",
        "No existing RF signal simulation pipeline",
        "Limited embedded ML inference experience"
    ],
    "tech_stack": ["Python", "C++", "FreeRTOS", "GNU Radio"],
    "recruiting_gaps": [
        "RF / Communications Engineer",
        "Embedded Systems Developer",
        "GIS / Geospatial Developer"
    ]
}

MOCK_CANDIDATES = [
    {
        "entity_id": "mapbox",
        "name": "Mapbox",
        "overall_score": 0.91,
        "matched_reasons": [
            "Provides geospatial mapping APIs directly applicable to ground station coverage",
            "Has a student/nonprofit grant program",
            "Active developer community with aerospace use cases"
        ]
    },
    {
        "entity_id": "gnuradio",
        "name": "GNU Radio Foundation",
        "overall_score": 0.87,
        "matched_reasons": [
            "Core tooling already in team's stack",
            "Open source contributors available for mentorship",
            "Strong overlap with RF subsystem blocker"
        ]
    },
    {
        "entity_id": "spire_global",
        "name": "Spire Global",
        "overall_score": 0.83,
        "matched_reasons": [
            "Commercial nanosatellite operator with student outreach history",
            "Can provide real RF data sets for simulation",
            "Recruiting pipeline overlap"
        ]
    },
    {
        "entity_id": "esri",
        "name": "Esri",
        "overall_score": 0.78,
        "matched_reasons": [
            "Industry-leading GIS platform",
            "Free licenses available for student teams",
            "Directly addresses geospatial mapping gap"
        ]
    },
    {
        "entity_id": "arm",
        "name": "Arm Ltd.",
        "overall_score": 0.74,
        "matched_reasons": [
            "Embedded ML toolchain (CMSIS-NN) targets FreeRTOS systems",
            "University program provides hardware and support",
            "Addresses embedded ML inference gap"
        ]
    }
]

MOCK_EXPLANATIONS = {
    "mapbox": {
        "entity_name": "Mapbox",
        "why_it_helps": [
            "Provides satellite ground track and coverage visualization APIs",
            "Supports real-time geospatial data rendering for mission control dashboards",
            "Well-documented SDKs compatible with the team's Python stack"
        ],
        "why_they_may_care": [
            "Student teams are high-visibility advocates for developer tools",
            "Aerospace use cases are a growth vertical for Mapbox",
            "Low-cost engagement with potential future enterprise customers"
        ],
        "recommended_ask": "Request access to Mapbox's student grant program for API credits and a 30-minute intro call with their developer relations team."
    },
    "gnuradio": {
        "entity_name": "GNU Radio Foundation",
        "why_it_helps": [
            "Core RF signal processing framework already in team's stack",
            "Community contributors can accelerate the signal simulation pipeline",
            "Extensive documentation and existing satellite communication blocks"
        ],
        "why_they_may_care": [
            "Supporting student satellite teams demonstrates real-world GNU Radio impact",
            "UW Orbital's work could contribute back as open source blocks",
            "Aligns with foundation's mission to grow the SDR community"
        ],
        "recommended_ask": "Reach out to the GNU Radio mailing list for a mentorship connection with a contributor experienced in satellite link budgets."
    }
}

MOCK_RECRUIT_GAPS = [
    {
        "role": "RF / Communications Engineer",
        "reason": "No current team member has RF hardware or link budget experience. Critical for ground station subsystem."
    },
    {
        "role": "Embedded Systems Developer",
        "reason": "FreeRTOS integration on the OBC requires low-level C++ expertise not present in current roster."
    },
    {
        "role": "GIS / Geospatial Developer",
        "reason": "Ground station coverage mapping is blocked without someone experienced in geospatial tooling."
    }
]

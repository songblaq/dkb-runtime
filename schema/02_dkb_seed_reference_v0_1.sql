-- DKB seed reference data v0.1

INSERT INTO dkb.dimension_model (model_key, version, description, config, is_active)
VALUES (
    'dg-v0-1',
    '0.1.0',
    'Default Directive Graph dimension model for DKB v0.1',
    jsonb_build_object(
        'groups', jsonb_build_array(
            'form','function','execution','governance','adoption','clarity'
        ),
        'score_range', jsonb_build_object('min',0.0,'max',1.0),
        'confidence_range', jsonb_build_object('min',0.0,'max',1.0)
    ),
    TRUE
)
ON CONFLICT (model_key) DO NOTHING;

INSERT INTO dkb.pack (pack_key, pack_name, pack_goal, pack_type, selection_policy, status)
VALUES
(
    'safe-starter',
    'Safe Starter Pack',
    '초보자가 안전하게 시작할 수 있는 기본 세트',
    'starter',
    jsonb_build_object(
        'trust_state', jsonb_build_array('verified'),
        'legal_state', jsonb_build_array('clear','custom'),
        'exclude_recommendation_state', jsonb_build_array('excluded','deprecated')
    ),
    'draft'
),
(
    'review-focused',
    'Review Focused Pack',
    'review 성향과 clarity가 높은 세트',
    'role',
    jsonb_build_object(
        'score_min', jsonb_build_object(
            'function.review', 0.70,
            'clarity.description_clarity', 0.60
        )
    ),
    'draft'
),
(
    'planning-workflow',
    'Planning Workflow Pack',
    'planning과 workflow 성향이 높은 세트',
    'role',
    jsonb_build_object(
        'score_min', jsonb_build_object(
            'function.planning', 0.70,
            'form.workflowness', 0.60
        )
    ),
    'draft'
)
ON CONFLICT (pack_key) DO NOTHING;

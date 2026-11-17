def subsidy_decision(store, household, charge_cents):
    if charge_cents < 0:
        raise ValueError('费用不能为负')
    rows = [row for row in store.all('income') if row['household'] == household and row['verified_cents'] is not None]
    if not rows:
        return {'household': household, 'status': 'needs_verification', 'cents': None}
    income = max(rows, key=lambda row: row['date'])['verified_cents']
    policy = store.get('policies', 'current')
    amount = min(charge_cents, policy['max_cents']) if income <= policy['income_limit_cents'] else 0
    return {'household': household, 'status': 'verified', 'cents': amount}


def approve_subsidy(store, household, charge_cents, reference):
    existing = [row for row in store.all('awards') if row['id'] == reference]
    if existing:
        if existing[0]['household'] != household or existing[0]['charge_cents'] != charge_cents:
            raise ValueError('发放编号对应不同申请')
        return existing[0]
    decision = subsidy_decision(store, household, charge_cents)
    if decision['status'] != 'verified':
        raise ValueError('收入尚未核验')
    row = {**decision, 'id': reference, 'charge_cents': charge_cents}
    store.put('awards', row, expected=0)
    return row

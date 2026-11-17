def eligible_households(store, day):
    return [row for row in store.all('households') if row['eligible_from'] <= day and (row['eligible_until'] is None or day < row['eligible_until'])]


def family_needs(store, household):
    store.get('households', household)
    needs = {}
    for row in store.all('residents'):
        if row['household'] == household:
            for service, hours in row['needs'].items():
                needs[service] = needs.get(service, 0) + hours
    return needs


def save_income(store, row):
    store.get('households', row['household'])
    if row['lower_cents'] is not None and row['upper_cents'] is not None and row['lower_cents'] > row['upper_cents']:
        raise ValueError('收入区间倒置')
    if row['verified_cents'] is not None and row['verified_cents'] < 0:
        raise ValueError('核验收入不合法')
    return store.put('income', row)

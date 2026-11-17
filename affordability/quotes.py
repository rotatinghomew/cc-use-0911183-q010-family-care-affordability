def service_quote(store, household, basket):
    family = store.get('households', household)
    cents = 0
    time = 0
    for service, count in basket.items():
        item = store.get('services', service)
        if count < 0 or family['area'] not in item['areas']:
            raise ValueError('服务不可获得或数量不合法')
        cents += item['cents_per_hour'] * count
        time += item['family_minutes_per_hour'] * count
    return {'household': household, 'cents': cents, 'family_minutes': time, 'within_time': time <= family['available_minutes']}

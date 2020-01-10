import dnf
base = dnf.Base()
base.fill_sack()
q = base.sack.query()
base.fill_sack()
q = base.sack.query()
all_installed = list(q.installed())
print(all_installed)
all_installed = [p for p in all_installed if p.name in ('python3-devel', 'python36-devel')]
p = all_installed[0]

for k in dir(p):
    try:
        print('%s => %s' % (k, getattr(p, k)))
    except Exception as exp:
        print('%s => oups: %s' % (k, exp))

print('PACKAGE: %s' % p.name)
provides = p.provides
for prov in provides:
    print('Looking at provide:%s' % prov)
    #pck_provides = q.filter(provides=prov).run()
    pck_provides = q.filter(prov).run()
    print('Result:%s' % pck_provides)
    for pck_provide in pck_provides:
        print(' - %s' % pck_provide.name)


# yum install -y python3-devel && python spike/test_dnf.py


# yum provides python3-devel  ?



import rpm
ts = rpm.TransactionSet()
mi = ts.dbMatch()
possibles = [h for h in mi]
possibles
p.provides
p['name']
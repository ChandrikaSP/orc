from fabric import task


@task
def nginx(c, password, branch_name, ref='master', mode=''):
    c.user = 'iuser'
    c.connect_kwargs.password = password

    nginx_folder = '~/ilcm/orc_nginx/load_balancer/'  # on base:worker
    c.run('echo "######## Updating code base"')
    with c.cd(nginx_folder):
        c.run('git fetch --all')
        c.run('git checkout {}'.format(ref))

    mode = mode.split('-')
    if "static" in mode:
        c.run('echo "######## Replacing static files"')
        branch_name = "prod" if branch_name == "master" else "staging"
        c.sudo("rm -rf /var/www/{}/static".format(branch_name), password=password)
        c.sudo("cp -R {}static /var/www/{}/".format(nginx_folder, branch_name), password=password)
    if "config" in mode:
        c.run('echo "######## Copying config files"')
        c.sudo("cp -R {}snippets/* /etc/nginx/snippets/".format(nginx_folder), password=password)
        c.sudo("cp -R {}sites-available/* /etc/nginx/sites-available/".format(nginx_folder), password=password)
        c.run('echo "######## Testing config files"')
        c.sudo("nginx -t", password=password)
        c.run('echo "######## Reloading nginx"')
        c.sudo("systemctl reload nginx.service", password=password)
        c.sudo("systemctl status nginx.service", password=password)


@task
def deploy(c, password, staging=False, ref='master', mode=''):
    """fab -H <master_node_ip> deploy -p <master_node_password> -r <commit_number> -m <deploy_mode> -s
    http://docs.fabfile.org/en/2.4/
    :param c: fabric.Connection
    :param password: k8s master node password.
    :param staging: Deploy on staging or on production
    :param ref: Branch name or commit number to checkout and deploy.
    :param mode: Deploy mode.
    :return:
    """
    c.user = 'iuser'
    c.connect_kwargs.password = password

    format_dict = {
        'env': 'staging' if staging else 'production',
        '_test': '_test' if staging else '',
        '-test': '-test' if staging else ''
    }
    remote_project_root = '~/ilcm/orc_staging' if staging else '~/ilcm/orc'  # on master
    with c.cd(remote_project_root):
        mode = mode.split('-')
        if 'fetch_co' in mode:
            c.run('git fetch --all')
            c.run('git checkout {}'.format(ref))
        if 'galleryapp' in mode or 'gallerytestapp' in mode or \
           'galleryconf' in mode or 'gallerytestconf' in mode:
            if 'galleryconf' in mode or 'gallerytestconf' in mode:
                c.run('kubectl create secret generic gallery-config '
                      '--from-file=gallery/_secret_config{_test}.py '
                      '--namespace=gallery{-test}-ns '
                      '-o yaml --dry-run | kubectl replace -f -'.format(**format_dict))
                c.run('kubectl delete deployment gallery{-test} '
                      '--namespace=gallery{-test}-ns'.format(**format_dict))
            c.run('kubectl apply -f gallery/config{_test}.yaml '
                  '--namespace=gallery{-test}-ns'.format(**format_dict))
        if 'galleryarchives' in mode and not staging:
            c.run('kubectl apply -f gallery/cron_job.yaml -n gallery-ns')
        if 'jhubns' in mode or 'jhubtestns' in mode:
            c.run('helm repo update')
            c.run('helm dependency update gesishub/gesishub')
            c.run('helm upgrade --install --namespace=jhub{-test}-ns jhub{-test} gesishub/gesishub '
                  '--wait --force --debug --timeout=360 '
                  '-f gesishub/config{_test}.yaml '
                  '-f gesishub/_secret{_test}.yaml '.format(**format_dict))
        if 'bhubns' in mode or 'bhubtestns' in mode:
            c.run('helm repo update')
            c.run('helm dependency update gesisbinder/gesisbinder')
            c.run('helm upgrade --install --namespace=bhub{-test}-ns bhub{-test} gesisbinder/gesisbinder '
                  '--wait --force --debug --timeout=360 '
                  '-f gesisbinder/config{_test}.yaml '
                  '-f gesisbinder/_secret{_test}.yaml '.format(**format_dict))
        if 'bhubupgrade' in mode and not staging:
            c.run('kubectl apply -f gesisbinder/bot/_secret_cron_job.yaml -n bhub-ns')
            c.run('kubectl apply -f gesisbinder/bot/cron_job.yaml -n bhub-ns')
        if 'prometheus' in mode and not staging:
            c.run('helm upgrade prometheus stable/prometheus --version=9.7.4 '
                  '-f monitoring/prometheus_config.yaml '
                  '--wait --force --debug --timeout=360')
        if 'grafana' in mode and not staging:
            c.run('helm upgrade grafana stable/grafana --version=4.3.0 '
                  '-f monitoring/grafana_config.yaml '
                  '-f monitoring/_secret_grafana.yaml '
                  '--wait --force --debug --timeout=360')


@task
def test(c, password, staging=False, ref='master', mode=''):
    """
    fab -H '194.95.75.8' test -s
    http://docs.fabfile.org/en/2.4/
    """
    c.user = 'iuser'
    c.connect_kwargs.password = password
    remote_project_root = '~/ilcm/orc_staging' if staging else '~/ilcm/orc'
    with c.cd(remote_project_root):
        c.run('pwd')
        c.run('ls -alh')

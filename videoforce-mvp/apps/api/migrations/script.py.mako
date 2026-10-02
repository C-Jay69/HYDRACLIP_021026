# template for revision files
# this is rendered as a python script

def upgrade():
    ## auto-generated commands - BEGIN
    % if upgrade_cmd is not none:
    %(upgrade_cmd)s
    % endif
    ## auto-generated commands - END


def downgrade():
    ## auto-generated commands - BEGIN
    % if downgrade_cmd is not none:
    %(downgrade_cmd)s
    % endif
    ## auto-generated commands - END
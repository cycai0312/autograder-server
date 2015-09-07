function register_group(project)
{
    console.log('register_group');
    console.log(project);
    var registered = $.Deferred();

    if (project.data.attributes.max_group_size === 1)
    {
        var members = [project.meta.username];
        submit_group_request(
            members, project
        ).done(function(group) {
            registered.resolve(group);
        });
    }
    else
    {
        lazy_get_template(
            'register-group-view'
        ).then(function(template) {
            return _render_and_process_group_registration_view(project, template);
        }).done(function(group) {
            registered.resolve(group);
        });
    }

    return registered.promise();
}

function submit_group_request(members, project)
{
    console.log('submit_group_members');

    var group_registered = $.Deferred();
    // console.log(members);
    // console.log(project);
    var request_data = {
        'data': {
            'type': 'submission_group',
            'attributes': {
                'members': members,
            },
            'relationships': {
                'project': {
                    'data': {
                        'type': 'project',
                        'id': project.data.id
                    }
                }
            }
        }
    }

    $.postJSON(
        "/submission-groups/submission-group/", request_data
    ).done(function(group) {
        console.log('resolving');
        group_registered.resolve(group);
    }).fail(function(data) {
        // console.log(data);
        var response_json = data.responseJSON;
        // console.log(data.responseJSON);
        // console.log(response_json.errors.meta);
        var error_html = '<div class="error"><div>Errors</div><ul>'
        $.each(response_json.errors.meta.members, function(i, message) {
            error_html += $('<li/>').text(message).html();
        });
        error_html += '</ul></div></div>';
        // console.log(error_html);
        $('#partner-list').after(error_html);
    });

    return group_registered.promise();
}

function _render_and_process_group_registration_view(project, template)
{
    console.log('_render_and_process_group_registration_view');
    console.log(project);
    console.log(template);

    var rendered = template.render(project);
    $('#main-area').html(rendered);
    $('#loading-bar').hide();
    // var registration_view_rendered = render_and_fix_links(
    //     'register-group-view', {'max_group_size': max_size});

    var group_registered = $.Deferred();

    // _initialize_group_registration_view(project, group_registered);
    // registration_view_rendered.done(function() {
    //     initialize_group_registration_view(
    //         min_size, max_size, project);
    // }).done(function() {
    //     deferred.resolve
    // });
    $('#register-group-button').click(function(e) {
        _register_group_button_click_handler(e, project, group_registered);
    });

    $('#work-alone-box').click(function() {
        if ($(this).is(':checked'))
        {
            $('#partner-list').hide();
            return;
        }
        $('#partner-list').show();
    });


    return group_registered.promise();
}

function _register_group_button_click_handler(e, project, deferred)
{
    // event.preventDefault();
    console.log('_register_group_button_click_handler');
    $(".error").remove();

    var members = [project.meta.username];
    if ($('#work-alone-box').is(':checked'))
    {
        submit_group_request(members, project).done(function(group) {
            deferred.resolve(group);
        });
        return;
    }

    $('#register-group-form :text').each(function(i, field) {
        if (field.name !== 'members')
        {
            return;
        }
        var email = $.trim(field.value);
        if (email === '')
        {
            // Skip blank fields
            return;
        }

        if (!is_umich_email(email))
        {
            $(this).after('<span class="error">Please enter a "umich.edu" email address</span>');
            return;
        }
        members.push(field.value);
    });

    var max_size = project.data.attributes.max_group_size;
    if (members.length > max_size)
    {
        $('#partner-list').append(
            '<div>Please enter at most ' + String(max_size - 1) +
            ' email(s)</div>');
        return;
    }
    var min_size = project.data.attributes.min_group_size;
    if (members.length < min_size || members.length === 0)
    {
        $('#partner-list').append(
            '<div class="error">Please enter at least ' +
            String(min_size - 1) + ' email(s)</div>');
        return;
    }

    submit_group_request(members, project).done(function(group) {
        deferred.resolve(group);
    });
}
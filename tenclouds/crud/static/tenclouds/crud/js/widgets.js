crud.view.Widget = crud.view.View.extend({

    tagName: 'div',
    className: 'inline'

});


crud.view.ModalWindow = crud.view.View.extend({

    className: 'crud-modalwindow',

    template: crud.template('/statics/tenclouds/crud/ejs/modalwindow.ejs'),

    events: {
        'click .close': 'close',
        'click .confirm': 'confirm'
    },

    initialize: function () {
        /*var args = Array.prototype.slice.call(this);
        crud.view.View.prototype.initialize.call(args);*/
        var active = crud.view.ModalWindow._activeInstance;
        if (active) {
            active.close();
        }
        crud.view.ModalWindow._activeInstance = this;

        _.bindAll(this, 'close', 'render', 'confirm');
    },

    close: function (e) {
        if (this.options.onClose) {
            this.options.onClose.call(this, this, e);
        }
        // cleanup! - remove from DOM
        this.remove();
        delete crud.view.ModalWindow._activeInstance;
    },

    confirm: function (e) {
        if (this.options.onConfirm) {
            this.options.onConfirm.call(this, this, e);
        }
        this.remove();
    },

    popup: function () {
        // auto add to DOM
        this.render();
        $(this.el)
            .appendTo('body');
        $(this.el).find("[type=text]").first().trigger('focus');
    },

    render: function () {
        var that = this;

        var content = {header: '', body: '', footer: ''};
        _.extend(content, this.options.content || {});
        crud.view.View.prototype.render.call(this, {content: content});

        this.displayOverlay();

        return this;
    },

    displayOverlay : function () {
        var that = this;
        var $w = $(window);
        var $d = $(document);

        this.$('.modal-well')
            .css({
                width: $d.width(),
                height: $d.height()
            })
            .click(function () {
                that.close();
            });

        $w.resize(function(){
            that.$('.modal-well')
                .css({
                    width:$d.width(),
                    height:$d.height()
            });
        });
    },

    setContent: function(c){
        this.options.content.body = c;
        this.render();
    }

});
crud.view.ModalWindow._activeInstance = null;


crud.view.DropdownMenuWidget = crud.view.Widget.extend({

    activatorSelector: '.crud-dropdown-toggle',

    dropdownSelector: '.crud-dropdown',

    render: function () {
        var events = _.extend({}, this.events);
        events['click ' + this.activatorSelector] = 'dropdownToggle';
        this.delegateEvents(events);
        return crud.view.Widget.prototype.render.call(this);
    },

    activatorDisabled: function (toSet) {
        var $e = this.$(this.activatorSelector);
        if (toSet !== undefined) {
            if (toSet) {
                $e.addClass('disabled');
            } else {
                $e.removeClass('disabled');
            }
        }
        return $e.hasClass('disabled');
    },

    dropdownActive: function (activate) {
        var $dropdown = this.$(this.dropdownSelector);
        if (activate === true) {
            $dropdown.show();
        } else if (activate === false) {
            $dropdown.hide();
        }
        return $dropdown.is(':visible');
    },

    dropdownToggle: function (e) {
        if (e) {
            e.preventDefault();
        }
        if (this.activatorDisabled()) {
            return false;
        }

        var $activator;
        if (e) {
            $activator = $(e.target);
        } else {
            $activator = $(this.el);
        }

        var $dropdown = this.$(this.dropdownSelector)
                .css({
                    //left: $activator.offset().left,
                    minWidth: $activator.innerWidth()
                })
                .toggle();
        if (this.dropdownActive()) {
            $activator.addClass('active');
            setTimeout(function () {
                $(document).one('click', function () {
                    $dropdown.hide();
                    $activator.removeClass('active');
                });
            }, 100);
        } else {
            $activator.removeClass('active');
        }
    }

});


crud.view.LabelActions = crud.view.DropdownMenuWidget.extend({

    template: crud.template('/statics/tenclouds/crud/ejs/label_actions.ejs'),

    events: {
        'click .apply-changes': 'applyChanges',
        'click .create-label': 'createLabel'
    },

    initialize: function () {
        _.bindAll(this, 'render', 'applyChanges', 'createLabel', 'actionDone');
        this.actionsInProgress = 0;

        this.labelViews = [];
        this.labelCollection = this.options.labelCollection;
        this.collection.bind('change:_selected', this.render);
    },

    render: function () {
        crud.view.DropdownMenuWidget.prototype.render.call(this);

        if (this.collection.some(function (m) { return m.get('_selected'); })) {
            this.activatorDisabled(false);
        } else {
            this.activatorDisabled(true);
        }

        return this;
    },

    dropdownToggle: function (activate) {
        if (activate) {
            // cleanup old data first
            _.each(this.labelViews, function (v) {
                v.remove();
            });
            this.labelViews = [];

            var that = this;
            var $ul = this.$('ul:first');
            this.labelCollection.each(function (m) {
                console.log(m);
                var item = new crud.view.ThreeStateCheckbox({
                    state: that.labelState(m),
                    model: m
                });
                $ul.prepend(item.render().el);
                that.labelViews.push(item);
            });
        }
        crud.view.DropdownMenuWidget.prototype.dropdownToggle.call(this);
    },

    labelState: function (label) {
        // return 'on' 'off' or 'half' depending on given label state
        if (label.get('counter') === 0) {
            return 'off';
        }
        if (label.get('counter') === this.collection.total) {
            return 'on';
        }

        if (this.collection.allSelected === true) {
            // special case when we cannot find out the state
            return 'half';
        }

        var selected = 0;
        var that = this;
        var queryIds = (that.options.actionQuery) ? that.options.actionQuery.id : null;
        console.log(this.collection);
        var matched = this.collection.filter(function (m) {
            // only selected items matters
            if (!m.get('_selected') && !queryIds) {
                return false;
            }
            if (queryIds) {
                var found = queryIds.indexOf(m.id) !== -1;
                if (!found) {
                    return false;
                }
            }

            selected += 1;

            var isMatching = false;
            _.each(that.getLabels(m), function (l) {
                if (l.name === label.get('name')) {
                    isMatching = true;
                }
            });
            return isMatching;
        });

        if (matched.length === 0) {
            return 'off';
        }
        if (matched.length === selected) {
            return 'on';
        }
        return 'half';
    },

    applyChanges: function (e) {
        var changes = {};
        var changesSize = 0;
        _.each(this.labelViews, function (v) {
            if (v.initialState === v.state) {
                return;
            }
            changes[v.model.id] = v.state;
            changesSize += 1;
        });

        if (changesSize === 0) {
            // no changes, no action
            return;
        }

        var that = this;
        var actionName = $(e.target).find('input').val();

        var options = {
            success: that.actionDone,
            error: that.actionDone,
            data: changes
        };
        this.actionsInProgress += 1;
        this.render();
        this.collection.runAction('patch_labels', options, this.options.actionQuery);
    },

    createLabel: function (e) {
        var that = this;
        var dialog = new crud.view.ModalWindow({
            content: {
                header: 'Create new label',
                body: 'Type label name: <input type="text">'
            },
            onConfirm: function () {
                that.labelCollection.create({
                    name: this.$('input').val().split(/\s+/)[0]
                }, {
                    success: function () {
                        that.dropdownToggle(true);
                    }
                });
            }
        });
        dialog.popup();
    },

    // Extract an array of labels from model.
    // Override for custom behavior (by default: model.get('labels'))
    getLabels: function (model) {
        return model.get('labels').split(", ");
    },

    actionDone: function () {
        this.actionsInProgress -= 1;
        this.collection.fetch();
        this.labelCollection.fetch();
    }

});


crud.view.ActionsMenuWidget = crud.view.DropdownMenuWidget.extend({

    template: crud.template('/statics/tenclouds/crud/ejs/table_actions.ejs'),

    initialize: function (options) {
        this.actionsInProgress = 0;

        _.bindAll(this, 'onAction', 'actionDone');
    },

    events: {
        'click .crud-action': 'onAction'
    },

    onAction: function (e) {
        var actionName = $(e.target).parent().find('input').val();

        var action;
        for (var i=0; i<this.options.meta.actions.length; ++i) {
            action = this.options.meta.actions[i];
            if (action.codename === actionName) {
                break;
            }
        }

        if (action.form !== undefined) {
            return this.displayActionDialog(action);
        }

        var options = {success: this.actionDone, error: this.actionDone};
        if (this.data) {
            options.data = data;
        }
        this.actionsInProgress += 1;
        this.render();
        this.collection.runAction(actionName, options, this.options.actionQuery);
    },

    displayActionDialog: function (action, formHTML) {
        var that = this;
        var form = formHTML || action.form;

        var dialog = new crud.view.ModalWindow({
            content: {
                header: action.name,
                body: form
            },
            onConfirm: function (dialog, e) {
                var formData = {};
                dialog.$('input, textarea, select').each(function () {
                    formData[$(this).attr('name')] = $(this).val();
                });

                var done = function () {
                    that.actionDone();
                    that.render();
                };
                var error = function (resp) {
                    // wtf? why this can happen?
                    if (resp.status === 200) {
                        return done();
                    }

                    that.actionsInProgress -= 1;
                    var form = JSON.parse(resp.responseText);
                    that.displayActionDialog(action, form);
                    that.render();
                };

                var options = {success: done, error: error, data: formData};
                that.actionsInProgress += 1;
                that.render();
                that.collection.runAction(action.codename, options, that.options.actionQuery);
            }
        });
        dialog.popup();
    },

    actionDone: function() {
        this.actionsInProgress -= 1;
        this.collection.fetch();
    }

});



crud.view.SelectAllWidget = crud.view.Widget.extend({

    template: {
        render: function () {
            return '<a class="dense btn left"  href="#">All</a>'; }
    },

    events: {
        'click a': 'selectAll'
    },

    initialize: function () {
        _.bindAll(this, 'selectAll');
    },

    selectAll: function (e) {
        e.preventDefault();
        this.collection.each(function (m) {
            m.set({'_selected': true});
        });
    }

});



crud.view.SelectNoneWidget = crud.view.Widget.extend({

    template: {
        render: function () {
            return '<a class="dense btn right" href="#">None</a>';
        }
    },

    events: {
        'click a': 'selectNone'
    },

    initialize: function () {
        _.bindAll(this, 'selectNone');
    },

    selectNone: function (e) {
        e.preventDefault();
        this.collection.each(function (m) {
            m.set({'_selected': false});
        });
    }

});



// Very simple widget that renders button that on click, redirects to given
// `href` address.
//
// Use this widget, instead of extending base template, just to add additional
// buttons
crud.view.LinkWidget = crud.view.Widget.extend({

    events: {
        'click': 'onLinkClick'
    },

    initialize: function () {
        if (this.options.text === undefined) {
            throw "'text' parameter is required";
        }

        _.bindAll(this, 'onLinkClick');

        var templateStr = '<a class="btn ' + this.options.extraClass + '" href="' + (this.options.href || 'javascript://') + '">' + this.options.text + '</a>';
        this.template = {
            render: function () { return templateStr; }
        };
    },

    onLinkClick: function (e) {
        if (this.options.onClick !== undefined) {
            return this.options.onClick.call(this, e, this);
        }
    }

});


crud.view.ThreeStateCheckbox = Backbone.View.extend({

    tagName: 'li',

    className: 'label-action',

    events: {
        'click': 'stateChange'
    },

    template: crud.template('/statics/tenclouds/crud/ejs/three_state_input.ejs'),

    initialize: function () {
        _.bindAll(this, 'stateChange', 'render');

        this.state = this.options.state || 'off';
        this.initialState = this.state;
    },

    render: function () {
        var hasChanged = this.initialState !== this.state;
        var html = this.template.render({
            state: this.state,
            label: this.model.escape('name'),
            name: this.model.id,
            changed: hasChanged
        });
        $(this.el).html(html);
        return this;
    },

    stateChange: function (e) {
        e.preventDefault();
        switch (this.state) {
            case 'on':
                if (this.initialState === 'half') {
                    this.state = 'half';
                } else {
                    this.state = 'off';
                }
                break;
            case 'half':
                this.state = 'off';
                break;
            case 'off':
                this.state = 'on';
                break;
            default:
                throw "Unexpected Error in crud/js/widget.js:560";
        }
        this.render();
        return false;
    }

});



// Display active messages list, using crud.collection.Messages container
crud.view.ActiveMessages = crud.view.Widget.extend({

    className: 'active-messages',

    template: crud.template('/statics/tenclouds/crud/ejs/active_messages.ejs'),

    events: $.extend({
        'click .close': 'closeClicked'
    }, crud.view.Widget.prototype.events),

    initialize: function () {
        _.bindAll(this, 'render', 'closeClicked');

        this.collection.bind('reset', this.render);
        this.collection.bind('change', this.render);
    },

    closeClicked: function (e) {
        e.preventDefault();
        // do not self-remove from DOM because we won't be able to display new
        // messages. Instead clean collection and rerender - messages window
        // should disappear
        this.collection.remove(this.collection.pluck('id'));
        this.render();
    }

});

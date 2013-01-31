/**
* Provides an object capable of rendering the template of given name.
* @argument template_name Name of the template to get.
* @argument static_url Overrides crud.settings.static_url.
* @returns An object having render(ctx) method.
*/
crud.template = crud.template || function (template_name, static_url) {
    var t;
    return {
        render: function (ctx) {
            t = t || new EJS({
                url: crud.template.get_template_url(template_name, static_url)
            });
            var libraryCtx = {
                crud: crud,
                '$': jQuery,
                '_': _
            };
            var extendedCtx = $.extend(ctx || {}, libraryCtx);
            return t.render(extendedCtx);
        }
    };
};

/**
* Creates url to access the ejs template specified.
* @argument template_name Path relative to static_url, including the filename
                          and extension.
* @argument static_url Overrides crud.settings.static_url.
* @returns Complete template url.
*/
crud.template.get_template_url = crud.template.get_template_url || function(template_name, static_url){
    return (static_url || crud.settings.static_url) + '/' + template_name;
};

/**
* Wrapper of crud.template for getting builtin templates.
* The functions does assumes builtin templates can be found in
* crud.settings.template_path and have .ejs extension.
* @argument template_name Filename of the template to get, without extension.
* @returns An object having render(ctx) method.
*/
crud.crud_template = crud.crud_template || function (template_name) {
    return crud.template(crud.settings.template_path + '/' + template_name + '.ejs');
};


crud.util.isFilterGroupShowable = function (filterGroupInfo, hiddenColumns) {
    return _.any((filterGroupInfo.filters || []), function (filter) {
        return crud.util.isFilterShowable(filter, hiddenColumns);
    });
};


crud.util.isFilterShowable = function (filterInfo, hiddenColumns) {
    // column generated from filter key
    var keyColumn = (filterInfo.key || '').split(':')[0];
    // columnsAffected is now undefined, but in the future the filter can
    // publish the list of affected columns via tastypie schema. this may be
    // useful when filter operates on multiple columns, or key prefix does
    // not match the affected column
    var affectedColumns = filterInfo.affectedColumns || [keyColumn];
    if (_.difference(affectedColumns, hiddenColumns).length === 0) {
        // all affected columns are hidden - we can hide this filter.
        return false;
    }
    return true;
};


crud.view.View = Backbone.View.extend({

    customOptions: [],  // opts to be set when given in initialize's options

    initialize: function (options) {
        Backbone.View.prototype.initialize.call(this, options);
        var that = this;

        // Scan through customOptions and set ones given in the options
        // argument, if present (set as this object keys). This sets them
        // on "this" object.
        _.each(options, function(val, opt) {
            if (_.contains(that.customOptions, opt)) {
                that[opt] = val;
            }
        });
    },

    render: function (context) {
        var ctx = {
            model: this.model,
            collection: this.collection,
            view: this
        };
        if (context !== undefined) {
            _.extend(ctx, context);
        }

        $(this.el).html(this.template.render(ctx));
        return this;
    }

});


crud.view.TableRow = crud.view.View.extend({

    tagName: 'tr',

    className: 'crud-table-row',

    template: crud.crud_template('table_row'),

    events: {
        'click [name^=item_]': 'onToggle'
    },

    customOptions: ['hiddenColumns', 'tableView'],

    initialize: function (options) {
        crud.view.View.prototype.initialize.call(this, options);
        _.bindAll(this, 'render', 'onToggle', 'remove', 'dispose');
        this.model.bind('change', this.render);
        this.model.bind('remove', this.remove);
    },

    dispose: function () {
        if (this.model) {
            this.model.unbind('change', this.render);
            this.model.unbind('remove', this.remove);
        }
        if (this.options) {
            this.options = {};
        }
        if (this.tableView) {
            delete this.tableView;
        }
    },

    escapeCell: function (model, columnName) {
        if (this.tableView) {
            // delegate work to parent table view
            return this.tableView.escapeCell(model, columnName);
        } else {
            // fallback
            return model.display(columnName);
        }
    },

    onToggle: function (e) {
        this.model.set({'_selected': !this.model.get('_selected')});
    },

    render: function (context) {
        var ctx = {
            meta: this.options.meta,
            hiddenColumns: (this.hiddenColumns || [])
        };
        if (context !== undefined) {
            _.extend(ctx, context);
        }
        crud.view.View.prototype.render.call(this, ctx);

        if (this.model.get('_selected')) {
            $(this.el).addClass('selected');
        } else {
            $(this.el).removeClass('selected');
        }

        return this;
    }

});


/**
 * Paginator view.
 *
 * Params (custom options):
 *  - isGlobal - (true/false) - Use the paginator as global and make it set
 *    and follow window's URL hashchanges. Only one global paginator should
 *    be created. Default: true (for compatibility reasons). This parameter
 *    can also be passed in initialize's method "options".
 *  - template - (crud.template) object - the template being rendered by the
 *    paginator object.
 *
 * TODO: MOAR DOCS
 */
crud.view.Paginator = crud.view.View.extend({

    className: 'crud-paginator',
    isGlobal: true,

    template: crud.crud_template('paginator'),

    events: {
        'click [class^=crud-paginator-page]': 'gotoPage',
        'click .crud-paginator-per-page li a': 'changePerPage'
    },

    customOptions: ["isGlobal", "template"],

    initialize: function (options) {
        // scan for and set customOptions
        crud.view.View.prototype.initialize.call(this, options);

        _.bindAll(this, 'render', 'gotoPage', 'changePerPage');
        this.collection.bind('reset', this.render);

        // address hash changes should only work for global paginators.
        if(this.isGlobal) {
            // change current page if there's suggestion in URL's hash
            var parts = document.location.hash.split('#');
            var rx = new RegExp('^/page-(\\d+)$');
            for (var i=1; i<parts.length; ++i) {
                var res = rx.exec(parts[i]);
                if (res) {
                    var page = parseInt(res[1], 10);
                    this.collection.page = page;
                    break;
                }
            }

            var that = this;

            $(window).bind('hashchange', function () {
                var pageNr = that.parseUrl();
                if (pageNr !== undefined && that.collection.page !== pageNr) {
                    that.collection.page = pageNr;
                    that.collection.fetch();
                }
            });
        }

    },

    parseUrl: function () {
        // return pagination page number from parsed url hash
        //
        var parts = document.location.hash.split('#');
        var rx = new RegExp('/page-(\\d+)');
        for (var i=1; i<parts.length; ++i) {
            var res = rx.exec(parts[i]);
            if (res) {
                return parseInt(res[1], 10);
            }
        }
    },

    updateUrl: function (pageNr) {
        // update URL's hash with current page info
        //
        // this can both overwrite any existing page info or create new one
        //
        var parts = document.location.hash.split('#');
        var rx = new RegExp('/page-(\\d+)');
        var updated = false;
        for (var i=1; i<parts.length; ++i) {
            var res = rx.exec(parts[i]);
            if (res) {
                if (this.collection.page === 1) {
                    parts.splice(i,i);
                } else {
                    parts[i] = '/page-' + this.collection.page;
                }
                updated = true;
                break;
            }
        }
        if (!updated && this.collection.page !== 1) {
            parts.push('/page-' + this.collection.page);
        }
        document.location.hash = parts.join('#');
    },

    gotoPage: function (e) {
        e.preventDefault();
        var cls = $(e.target).closest('[class^=crud-paginator-page-]').attr('class');
        if (cls.match(/disabled/)) {
            return;
        }
        var clsList = cls.split(' ');
        var pageNr;
        for (var i=0; i<clsList.length; ++i) {
            try {
                pageNr = parseInt(cls.match(/crud-paginator-page-(\d+)/)[1], 10);
            } catch (err) {
                continue;
            }
            break;
        }
        this.collection.page = pageNr;
        this.collection.fetch();
        if (this.isGlobal) {
            this.updateUrl();
        }
    },

    changePerPage: function (e) {
        this.collection.perPage = parseInt($(e.target).text(), 10);
        this.collection.fetch();
        return false;
    }

});



crud.view.TableFilter = crud.view.View.extend({

    template: crud.crud_template('table_filter')
});


crud.view.Table = crud.view.View.extend({

    itemViewClass: crud.view.TableRow,

    template: crud.crud_template('table'),

    widgets: {
        '.crud-meta-actions': [
            'crud.view.SelectAllWidget',
            'crud.view.SelectNoneWidget',
            'crud.view.ActionsMenuWidget'
        ],
        '.crud-table-paginator': [
            'crud.view.Paginator'
        ]
    },

    customOptions: ['hiddenColumns', 'columnDisplayers'],

    events: {
        'click .crud-sortable-column': 'onSortableClick'
    },

    columnDisplayers: {},

    initialize: function (options) {
        crud.view.View.prototype.initialize.call(this, options);
        this._initialized = false;
        _.bindAll(this, 'addOne', 'newItem', 'addAll', 'onSelected',
                  'onSelectedAll', 'onSortableClick', 'requestError','change',
                  'removeAllModelViews', 'escapeCell', 'showMessage', 'showMessageEmtpy');

        this.collection.bind('selected', this.onSelected);
        this.collection.bind('add', this.addOne);
        this.collection.bind('reset', this.addAll);
        this.collection.bind('reset:error', this.requestError);
        this.collection.bind('emtpy',this.showMessageEmtpy);
        this.modelViews = {};
    },

    addWidget: function (selector, widget) {
        if (this.widgets[selector] === undefined) {
            this.widgets[selector] = [widget];
        } else {
            this.widgets[selector].push(widget);
        }
    },

    removeWidget: function (selector, widget) {
        if (this.widgets[selector] !== undefined){
            this.widgets[selector] = _.without(this.widgets[selector], widget);
        }
    },

    requestError: function (err) {
        // Callback for request error singnals
        //
        // Just show error info for few seconds.
        this.showMessage('error', 'Server response error.', 5000);
    },

    addOne: function (model) {
        var v = this.newItem(model);
        model.view = v;
        this.modelViews['modelview-' + model.cid] = v;
        this.$('.crud-items').append(v.render().el);
    },

    newItem: function (model) {
        return new this.itemViewClass({
            meta: this.options.meta,
            hiddenColumns: this.hiddenColumns,
            tableView: this,
            model: model
        });
    },

    removeAllModelViews: function () {
        _.each(this.modelViews, function (view) {
            if (view.model && view.model.view && view.model.view === view) {
                delete view.model.view;
            }
            view.remove();
            view.dispose();
        });
        this.modelViews = {};
    },

    addAll: function () {
        this.removeAllModelViews();
        this.render({}, true);
        this.collection.each(this.addOne);
    },

    onSortableClick: function (e) {
        this.collection.querySortOrder($(e.target).find('input').val());
        this.collection.fetch();
    },

    onSelected: function (selectOn) {
        if (this.collection.total <= this.collection.length) {
            return false;
        }
        if (selectOn) {
            if (this.collection.allSelected) {
                this.showMessage('warning', '<strong>' + this.collection.total + '</strong> objects selected.');
            } else {
                this.showMessage('warning', '<strong>' + this.collection.length + '</strong> objects selected&nbsp;' +
                    '<a href="#" class="crud-select-all-items ">Select all ' + this.collection.total + '.</a>');
                this.delegateEvents({'click .crud-select-all-items': 'onSelectedAll'});
            }
        } else {
            this.hideMessage();
        }
    },

    // BUG: won't queue up messages properly. Just f***ed up.
    showMessage: function (msgType, htmlMessage, timeout) {
        var $infoRow = this.$('.crud-message-box');
        var $infoRowContents = $($infoRow.children()[0]);
        $infoRowContents.removeClass('error warning info success');
        if (timeout === 0) {
            $infoRow.fadeOut();
            return;
        }
        $infoRowContents.addClass(msgType);
        $infoRowContents.html(htmlMessage);
        $infoRow.fadeIn();
        var that = this;
        if (timeout !== undefined) {
            if (that._showMessageTimeout) {
                clearTimeout(that._showMessageTimeout);
                delete that._showMessageTimeout;
            }
            that._showInfoTimer = setTimeout(function () {
                $infoRow.fadeOut();
                delete that._showMessageTimeout;
            }, timeout);
        }
    },

    showMessageEmtpy: function(){
        this.showMessage('alert','Collection is empty',3000);
    },

    hideMessage: function () {
        this.showMessage(null, null, 0);
    },

    onSelectedAll: function () {
        this.collection.allSelected = true;
        this.collection.modelSelectChanged();
    },

    renderWidgets: function () {
        var that = this;
        _.each(this.widgets, function (widgetClasses, selector) {
            _.each(widgetClasses, function (widget) {
                var v;

                // because of import issues, widget class can be defined as
                // string
                if (typeof widget === 'string') {
                    widget = eval(widget);
                }

                // if widget was alredy initialize, do not try to do this
                // again
                if (widget.constructor === Function) {
                    v = new widget({
                        collection: that.collection,
                        meta: that.options.meta
                    });
                } else {
                    // using already initialized widget requires events
                    // redelegation
                    v = widget;
                    v.delegateEvents(v.events);
                }
                that.$(selector).append(v.render().el);
            });
        });
    },

    render: function (context, renderAll) {
        var ctx = {
            meta: this.options.meta,
            hiddenColumns: (this.hiddenColumns || [])
        };

        if (context !== undefined) {
            _.extend(ctx, context);
        }
        if (!this._initialized || renderAll) {
            this._initialized = true;
            crud.view.View.prototype.render.call(this, ctx);
            this.renderWidgets();
        }
        this.delegateEvents(this.events);
        return this;
    },

    escapeCell: function (model, columnName) {
        var meta = this.options.meta;
        var options, value, url, displayColumnValue, result;
        if (this.columnDisplayers[columnName]) {
            // using custom column displayer if available
            displayColumnValue = this.columnDisplayers[columnName];
            value = model.getComplex(columnName);
            if (meta.fieldsURL[columnName]) {
                url = model.get(meta.fieldsURL[columnName]);
            }
            options = {
                model: model,
                columnName: columnName,
                url: url,
                tableView: this
            };
            return displayColumnValue.call(this, value, options);
        }
        if (meta.fieldsURL[columnName]) {
            // url is defined, so wrap it in <a> tag
            result = '';
            result += '<a href="' + model.get(meta.fieldsURL[columnName]) + '">';
            result += model.display(columnName);
            result += '</a>';
            return result;
        } else {
            // delegate do model, for backward compatibility
            return model.display(columnName);
        }
    },

    change: function(){}

});


crud.view.LabelList = crud.view.View.extend({

    template: crud.crud_template('label_list'),

    events: {
        'change [type=checkbox]': 'onLabelChange'
    },

    initialize: function (options) {
        crud.view.View.prototype.initialize.call(this, options);
        this.filteredCollection = this.options.filteredCollection;

        _.bindAll(this, 'render', 'onLabelChange', 'updateFilter', 'resetBegin', 'resetEnd');
        this.collection.bind('reset', this.render);
        this.collection.bind('change', this.render);
        this.collection.bind('change:_selected', this.updateFilter);
        this.collection.bind('reset:begin', this.resetBegin);
        this.collection.bind('reset:end', this.resetEnd);
    },

    onLabelChange: function (e) {
        var $e = $(e.target);
        var m = this.options.collection.get($e.val());
        m.set({'_selected': $e.attr('checked')});
    },

    updateFilter: function () {
        var f = this.filteredCollection.queryFilter;
        var selected = this.collection.filter(function (m) {
            return m.get('_selected');
        });
        f.lf = _.map(selected, function (m) { return m.get('name'); });
        if (f.lf.length === 0) {
            delete f.lf;
        }
        this.filteredCollection.applyFilter(f);
        this.collection.applyFilter(f);
    },

    resetBegin: function () {
        // save "selected" state
        var selected = {};
        this.collection.each(function (m) {
            if (m.get('_selected')) {
                selected[m.id] = true;
            }
        });
        this._selected = selected;
    },

    resetEnd: function () {
        var that = this;
        var restored = false;
        // restore "selected" state after the fetch
        this.collection.each(function (m) {
            if (that._selected[m.id]) {
                m.set({'_selected': true}, {silent: true});
                restored = true;
            }
        });
        if (restored) {
            this.render();
        }
    }

});


crud.view.FullTextSearchItem = crud.view.View.extend({

    tagName: 'li',

    template: crud.crud_template('search_item'),

    events: {
        'search input': 'search',
        'keyup input': 'onKeyUp'
    },

    initialize: function (options) {
        crud.view.View.prototype.initialize.call(this, options);
        _.bindAll(this, 'onKeyUp', 'search', 'render');
    },

    clearSearchTrigger: function () {
        if (this._searchTrigger !== undefined) {
            clearTimeout(this._searchTrigger);
            delete this._searchTrigger;
        }
    },

    onKeyUp: function (e) {
        var that = this;

        this.clearSearchTrigger();
        this._searchTrigger = setTimeout(function() {
            delete that._searchTrigger;
            that.search();
        }, 1000);
    },

    search: function () {
        this.clearSearchTrigger();

        var val = this.$('input').val();

        if (this._lastSearchKey) {
            this.collection.removeFilter(this._lastSearchKey);
            delete this._lastSearchKey;
        }

        if (val.length > 0) {
            this._lastSearchKey = this.options.filter.key + ':' + val;
            this.collection.addFilter(this._lastSearchKey);
        }
        this.collection.fetch();
    },

    render: function () {
        var value = this.$('input').val() || '';
        $(this.el).html(this.template.render({key: this.options.filter.key, value: value}));
        return this;
    }

});


crud.view.ChoiceFilterItem = crud.view.View.extend({

    tagName: 'li',

    template: crud.crud_template('filter_item'),

    events: {
        'click': 'onFilterChange'
    },

    initialize: function (options) {
        crud.view.View.prototype.initialize.call(this, options);
        this.isActive = false;

        _.bindAll(this, 'onFilterChange');
    },

    onFilterChange: function (e) {
        this.isActive = !this.isActive;
        var key = this.options.filter.key;

        if (this.isActive) {
            this.collection.addFilter(key);
        } else {
            this.collection.removeFilter(key);
        }
        $('[name=ff]').remove();
        $.each(this.collection.queryFilter.filters, function(m,v){

            $('[name=lf]').after('<input type="hidden" name="ff" value="'+v.split(":")[1]+'">');
        });
        this.render();
        this.collection.fetch();
    }

});


crud.view.RadioFilterItem = crud.view.View.extend({

    tagName: 'li',

    template: crud.crud_template('radiofilter_item'),

    events: {
        'change': 'onFilterChange'
    },

    initialize: function (options) {
        crud.view.View.prototype.initialize.call(this, options);
        this.isActive = false;
        _.bindAll(this, 'onFilterChange');
    },

    onFilterChange: function (e) {
        $(e.target).parent().parent().find("li").removeClass("current");
        $(e.target).parents("li").addClass("current");
        var key = this.options.filter.key;
        var groupKey = this.options.filter.groupKey;

        if (this.collection.queryFilter.filters) {
            var prevRadioValue = -1;
            _.each(this.collection.queryFilter.filters, function (key, n) {
                if (key.split(':', 1)[0] === groupKey) {
                    prevRadioValue = n;
                }
            });
            if (prevRadioValue > -1) {
                this.collection.queryFilter.filters.splice(prevRadioValue,
                        prevRadioValue === 0 ? 1 : prevRadioValue);
            }
        }
        this.collection.addFilter(key);
        this.collection.fetch();
    },

    render: function () {
        crud.view.View.prototype.render.call(this);
        if(this.isActive === true){
            $(this.el).addClass("current");
        }
        return this;
    }

});


crud.view.RadioNoFilterItem = crud.view.RadioFilterItem.extend({

    initialize: function (options) {
        crud.view.RadioFilterItem.prototype.initialize.call(this, options);
        // active by default
        this.isActive = true;
    },

    onFilterChange: function (e) {
        $(e.target).parent().parent().find("li").removeClass("current");
        $(e.target).parents("li").addClass("current");
        var key = this.options.filter.key;
        var groupKey = this.options.filter.groupKey;

        if (this.collection.queryFilter.filters) {
            var prevRadioValue = -1;
            _.each(this.collection.queryFilter.filters, function (key, n) {
                if (key.split(':', 1)[0] === groupKey) {
                    prevRadioValue = n;
                }
            });
            if (prevRadioValue > -1) {
                this.collection.queryFilter.filters.splice(prevRadioValue,
                        prevRadioValue === 0 ? 1 : prevRadioValue);
            }
        }
        this.collection.fetch();
    }
});


// A map of standard CRUD widgets.
crud.view.standardFilterWidgets = {
    'choice': crud.view.ChoiceFilterItem,
    'text': crud.view.FullTextSearchItem,
    'radio:nofilter': crud.view.RadioNoFilterItem,
    'radio': crud.view.RadioFilterItem
};


// View: group of filters.
//
// Override with custom 'template' and 'appendTo' selector to override default h3/ul view.
// The filtering widgets will be appended to the $(appendTo) element.
//
// Template context takes only 'title'.
//
// Override 'filterWidgets' to change widgets that are displayed for CRUD collections.
// Standard filter widgets are defined in crud.view.standardFilterWidgets.
//
// A filter widget takes 'collection', 'meta' and 'filter' arguments.
// Each 'filter' should have: 'key', 'name', 'type' and, optionally 'groupKey' properties.
//
crud.view.FilterGroup = crud.view.View.extend({

    template: crud.crud_template('filter_group'),

    filterWidgets: crud.view.standardFilterWidgets,

    appendTo: 'ul',

    bindEvents: {},

    customOptions: ['hiddenColumns'],

    initialize: function (options) {
        crud.view.View.prototype.initialize.call(this, options);
        $(this.el).html(this.template.render({title: this.options.filters.title}));
        var $elem = $(this.el).find(this.appendTo);

        var that = this;

        _.each(this.options.filters.filters, function (filter) {
            // check if filter requires API access:
            // "type:api" or "type"
            var filterApi = filter.type.split(':api');

            // init widget for filter.
            var initWidget = function (filter) {
                if (!crud.util.isFilterShowable(filter, that.hiddenColumns)) {
                    return;
                }

                var widgetCls = that.filterWidgets[filterApi[0]];
                var widget = new widgetCls({
                    collection: that.options.collection,
                    meta: that.options.meta,
                    filter: filter
                });

                // bind widgets
                _.each(that.options.bind, function (callback, ev) {
                    widget.bind(ev, callback);
                });

                $elem.append(widget.render().el);
            };

            // no API access required
            if (filterApi.length === 1) {
                initWidget(filter);
            }
            else {
                // Get filter choices from API
                $.getJSON(filter.apiUrl, function (data) {
                    _.each(data.objects, function (obj) {
                        initWidget({
                            type: filter.type,
                            name: obj.name,
                            key: filter.key + ":" + obj[filter.filteredField]
                        });
                    });
                }); // getJSON
            } // else

        }); // each(filter)
    },

    render: function () {
        return this;
    }

});


// View: list of filter groups.
//
// Use 'filterGroupClass' option to provide custom FilterGroup class
// (a subclass of crud.view.FilterGroup).
//
// Use 'groupsAffected' option to optionally provide an array of group titles
// that will be handled by this FilterList. If 'groupsAffected' was not specified,
// all groups will be handled.
//
// Use 'bindEvents' option to have each widget event bound to some function.
//  {"event_name": event_handler_function, ...}
//
crud.view.FilterList = crud.view.View.extend({

    customOptions: ['hiddenColumns'],

    initialize: function (options) {
        crud.view.View.prototype.initialize.call(this, options);
        if (!this.options.filterGroupClass)
            this.options.filterGroupClass = crud.view.FilterGroup;

        var groupsAffected = this.options.groupsAffected;
        var bindEvents = this.options.bindEvents || {};
        var that = this;

        _.each(this.options.filterGroups, function (filterGroup) {
            if (!crud.util.isFilterGroupShowable(filterGroup, that.hiddenColumns)) {
                return;
            }
            if (_.isArray(groupsAffected) &&
                    groupsAffected.indexOf(filterGroup.title) === -1) {
                return;
            }
            var filterGroupClass = (filterGroup.filterGroupClass ||
                    that.options.filterGroupClass);
            var fg = new filterGroupClass({
                bind: bindEvents,
                collection: that.options.collection,
                meta: that.options.meta,
                hiddenColumns: that.hiddenColumns,
                filters: filterGroup
            });
            $(that.el).append(fg.render().el);
        });
    },

    render: function () {
        return this;
    }

});

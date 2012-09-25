// Utility function: return val if val is not a function, and function
// result if it is.
crud.util.getValue = function(val) {
    return _.isFunction(val) ? val() : val;
};


crud.modelMeta = function (baseUrl, callback) {
    $.getJSON(crud.util.getValue(baseUrl) + 'schema/', {}, function (resp) {
        callback(resp);
    });
};


crud.model.Model = Backbone.Model.extend({

    roundFloat: 3,  // round float? if so, how many places
    fixedFloat: false,  // whether to make rounded floats fixed
    placeholder: null,  // the placeholder for "null" values

    initialize: function(options) {
        _.each(["roundFloat", "fixedFloat", "placeholder"], function(name) {
            if (options.name)
                this.name = options.name;
        });
    },

    defaults: {
        '_selected': false
    },

    toJSON: function () {
        var obj = Backbone.Model.prototype.toJSON.call(this);
        delete obj['_selected'];
        return obj;
    },

    url: function () {
        var base;
        if (this.collection) {
            base = this.collection.urlRoot;
        } else {
            base = this.urlRoot;
        }

        // Wat. Husio, really?
        if (base === undefined) { xxx = this; }

        var baseVal = crud.util.getValue(base);

        if (this.isNew()) {
            return baseVal;
        }

        return baseVal + (baseVal.charAt(base.length - 1) == '/' ? '' : '/') + this.id;
    },

    // similar to Backbone.Model.escape, but respects django-like attribute
    // naming with __ separator as relation symbol, and can round float numbers.
    display: function (name) {
        var parts = name.split('__');
        var val = this.get(name);

        if (parts.length === 1) {
            if (this.roundFloat && _.isNumber(val)) {
                var factor = Math.pow(10, this.roundFloat);
                // little hack for rounding: see http://stackoverflow.com/a/661569
                var rounded = Math.round(val * factor) / factor;

                // fix float only if we want to and it's not an int
                // http://stackoverflow.com/a/3886106
                var fixFloat = (this.fixedFloat && rounded % 1 !== 0);

                return (fixFloat) ? rounded.toFixed(this.roundFloat) : rounded;
            }
            if (!val) {
                return this.placeholder;
            }
            return this.escape(name);
        }
        var elem = this.get(parts[0]);
        for (var i=1; i<parts.length; ++i) {
            elem = elem[parts[i]];
        }

        // from backbone.js
        var escapeHTML = function(s) {
            return s.replace(/&(?!\w+;)/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        };
        return escapeHTML(elem + '');
    }

});


crud.collection.PaginatedCollection = Backbone.Collection.extend({

    page: 1,

    perPage: 25,

    total: 0,

    fetch: function (options) {
        var that = this;
        var o = options || {};

        this.trigger('reset:begin');

        var success = o.success;
        // wrap default succes callback
        o.success = function (resp) {
            that.trigger('reset:end');
            if (success) {
                success(that, resp);
            }
        };
        Backbone.Collection.prototype.fetch.call(this, o);
    },

    parse: function (resp) {
        this.page = resp.page;
        this.total = resp.total;
        this.perPage = resp.per_page;
        this.ordering = resp.ordering;
        return resp.objects;
    },

    url: function () {
        var params = {page: this.page, per_page: this.perPage};
        return crud.util.getValue(this.urlRoot) + '?' + $.param(params, true);
    },

    hasNext: function () {
        if (this.total === null) {
            // if total is null, the API wishes not to provide total number of
            // arguments, so we don't really know if there is a next page
            // unless we get an empty one (call this "endless" stream)
            return this.models.length >= this.perPage;
        }
        return this.page * this.perPage < this.total;
    },

    hasPrev: function () {
        return this.page > 1;
    },

    numPages: function () {
        if (this.total === null) {
            // unspecified.
            return null;
        }
        return Math.ceil(this.total / this.perPage);
    }

});

crud.collection.Collection = crud.collection.PaginatedCollection.extend({

    model: crud.model.Model,

    // enable/disable pagination
    paginate: true,

    initialize: function () {
        this.allSelected = false;
        if(!this.queryFilter) {
            this.queryFilter = {filters: []};
        }

        _.bindAll(this, 'modelSelectChanged');
        this.bind('change:_selected', this.modelSelectChanged);

        var that = this;
        this.bind('reset:begin', function () { that.isRefreshing = true; });
        this.bind('reset:end', function () { that.isRefreshing = false; });
        this.isRefreshing = null;
    },

    parse: function (resp) {
        var orig = crud.collection.PaginatedCollection.prototype.parse.call(this, resp);
        if(!this.querySort) { this.makeOrderingDict(); }
        return orig;
    },

    modelSelectChanged: function (m) {
        if (this.all(function (m) { return m.get('_selected'); })) {
            this.trigger('selected', true);
        } else {
            this.allSelected = false;
            this.trigger('selected', false);
        }
    },

    fetch: function (options) {
        this.allSelected = false;
        var that = this;
        var o = options || {};
        // wrap default error callback
        var error = o.error;
        o.error = function (resp) {
            that.trigger('reset:error', resp);
            if (error) {
                error(that, resp);
            }
        };
        crud.collection.PaginatedCollection.prototype.fetch.call(this, o);
    },

    fetchMeta: function (callback) {
        // fetch model metadata
        var that = this;

        crud.modelMeta(this.urlRoot, function (meta) {
            // required by sorting plugins
            that.fieldsSortable = meta.fieldsSortable;
            callback(meta);
        });
    },

    selectedQuery: function () {
        var query = {
            id__in: [],
            filter: {}
        };

        query.filter = this.queryFilter;

        if (!this.allSelected) {
            this.each(function (m) {
                if (m.get('_selected')) {
                    query.id__in.push(m.id);
                }
            });
        }

        query.sort = this.querySortAsList();

        return query;
    },

    /**
    * Converts the input ordering list into querySort structure and sets
    * this.querySort to the correct value.
    *
    * This version supports only a single sorting field, thus only
    * this.ordering[0] is used.
    */
    makeOrderingDict: function() {
        if (this.ordering && this.ordering[0]) {
            var field = this.ordering[0];
            var is_reverse = field[0] === '-';
            var value = is_reverse ? 'down' : 'up';
            var clean_field = is_reverse ? field.substring(1) : field;
            this.querySort = {};
            this.querySort[clean_field] = value;
        }
    },

    /**
    * Converts this.querySort to a form that can be sent to the server.
    *
    * Plugins using a more sophisticated querySort structure should override
    * this method.
    *
    * @returns An array of sorting variables with optional '-' prefix for
    * reverse ordering, eg. ['title', '-name']. Should return a falsy value or
    * an empty array if this.querySort does not contain any valid sorting
    * field definition.
    */
    querySortAsList: function() {
        return this.querySortToDjango();
    },

    /**
    * Changes the current active query sorting, either by reversing or applying
    * a new sorting field.
    *
    * Basic implementation supports sorting only by a single column.
    * @argument sortField The field to toggle or set.
    */
    querySortOrder: function (sortField, set) {
        if (!sortField) return;
        var result = {};
        if(this.querySort && this.querySort[sortField] === 'up') {
            result = 'down';
        } else {
            result = 'up';
        }
        this.querySort = {};
        this.querySort[sortField] = result;
    },

    /**
    * Converts self.querySort to a list of django-friendly sorting filters.
    * @returns An array of strings, eg: ['title', '-date'].
    */
    querySortToDjango: function() {
        var results = [];
        if (this.querySort) {
            var that = this;
            // using fieldsSortable allows to pass the columns in the order
            // specified by the handler, it's a nice to have feature for any
            // overrides
            _.each(this.fieldsSortable, function(sorter){
                var val = that.querySort[sorter];
                if (val === undefined){
                    return;
                } else if (val === 'up'){
                    results.push(sorter);
                } else if (val === 'down'){
                    results.push('-' + sorter);
                }
            });
        }
        return results;
    },

    url: function () {
        var params = this.paginate ? {page: this.page, per_page: this.perPage} : {};

        order_by = this.querySortAsList();
        if (order_by && order_by.length > 0){
            params.order_by = order_by;
        }

        params = $.extend(params, this.queryFilter);

        var urlParams = $.param(params, true);
        var url = crud.util.getValue(this.urlRoot);

        return (urlParams) ? url + '?' + urlParams : url;
    },

    applyFilter: function (f, preventFetch) {
        this.queryFilter = f || {};
        this.trigger('filterChange');

        if (preventFetch)
            return;

        // because fetch may return the same objects and we dont want to lose
        // _selected attribute, update fetched data if required
        var beforeFetch = this.toArray();
        var that = this;
        this.fetch({
            success: function () {
                _.each(beforeFetch, function (oldModel) {
                    if (oldModel.get('_selected') !== true) {
                        return;
                    }
                    var m = that.get(oldModel.id);
                    if (m) {
                        m.set({'_selected': true}, {silent: true});
                    }
                });
                that.trigger('reset');
            },
            silent: true
        });
    },

    // Run action on given collection
    //
    // Given action need to be provided by collection handler
    runAction: function (actionName, options, query) {
        var that = this;
        query = query || this.selectedQuery();
        var o = options || {};
        // options.data should not overwrite our data
        var options_data = options.data || {};
        delete options.data;

        // Whenever we run action, server might response with spawned offline
        // task status key. If he does, trigger global event with that key, so
        // that everybody would know about it.
        var success = o.success;
        o.success = function (resp) {
            if (resp && resp.length > 0) {

                if (resp.statuskey) {
                    crud.event.Task.trigger('new', resp.statuskey, resp);
                }

                if (resp.redirect_url){
                    window.location = resp.redirect_url;
                }
            }

            if (success) {
                success(that, resp);
            }
        };

        o = _.extend({
            url: this.url().split('?')[0] + '_actions/',
            data: JSON.stringify({
                action: actionName,
                query: query,
                data: options_data
            })
        }, o);
        Backbone.sync('create', this.collection, o);
    },

    // Special version of "runAction" function for downloading stuff.
    // Handles requests in such a way that the browser notices
    // "Content-Disposition" response header.
    //
    // TODO: this should be done automagically, and specified in CRUD
    // handler. It is quite a hell to do that, however.
    runDownloadAction: function (actionName, options) {
        var data = JSON.stringify({
            action: actionName,
            query: this.selectedQuery(),
            data: options.data || {}
        });

        var url = this.url().split('?')[0] + '_actions/';

        // construct the inputs for form
        var inputs = '<input type="hidden" name="data" value=' + data + ' />';

        //send request using hidden form, and remove it
        jQuery('<form action="' + url + '" method="post">' + inputs + '</form>')
            .appendTo('body').submit().remove();
    },

    addFilter: function (key) {
        if (!this.queryFilter.filters) {
            this.queryFilter.filters = [];
        }

        this.queryFilter.filters.push(key);
    },

    removeFilter: function (key) {
        var indexOf = _.indexOf(this.queryFilter.filters, key);
        if (indexOf > -1) {
            this.queryFilter.filters.splice(indexOf, indexOf === 0 ? 1 : indexOf);
        }
    },

    removeFilterByKey: function (key) {
        this.queryFilter.filters =  _.reject(this.queryFilter.filters,
                function(filterKey) {
                    return filterKey.search(key) !== -1;
                }
        );
    }

});




crud.model.Message = crud.model.Model.extend({

    isCompleted: function () {
        // we cannot check state of models with no id anyway
        return (this.id === undefined);
    }

});


crud.collection.Messages = crud.collection.Collection.extend({

    model: crud.model.Message,

    checkInterval: 1500,

    initialize: function () {
        var args = Array.prototype.slice.call(arguments);
        crud.collection.Collection.prototype.initialize.call(this, args);

        _.bindAll(this, 'onNewTask');

        crud.event.Task.bind('new', this.onNewTask);
    },

    repeatFetch: function () {
        return !!this.length && this.any(function(m) {
            return !m.isCompleted();
        });
    },

    onNewTask: function (statusKey, resp) {
        var data = {id: statusKey};
        _.extend(data, resp);
        var m = new this.model(data);
        this.add(m);
        this.update();
    },

    update: function () {
        // for every model in collection, check if it's completed. If yes,
        // remove from collection, else call 'fetch' method

        var that = this;
        var ids = this.pluck('id');

        _.each(ids, function (mId) {
            var m = that.get(mId);
            if (m.isCompleted()) {
                that.remove(m);
                return;
            }
            var success = function (m, resp) {
                if (that.repeatFetch() && that.checkInterval > 0) {
                    setTimeout(function () {
                        m.fetch({success: success, error: error});
                    }, that.checkInterval);
                }
            };
            var error = function (m, resp) {
                setTimeout(function() {
                    m.fetch({success: success, error: error});
                }, 2000);
            };

            m.fetch({success: success, error: error});
        });
        this.trigger('reset', 'update');
    }

});

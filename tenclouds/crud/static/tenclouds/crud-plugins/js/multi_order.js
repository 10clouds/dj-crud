/**
* Multi-field ordering CRUD plugin.
*
* Basic CRUD collection ordering behaviour supports only a single ordering
* field/column. If default_ordering resource parameter is set, only the first
* item would be reflected by the sorting fields.
*
* This plugin adds the option to order by any number of columns included in
* the resource's Meta.ordering. The order of sorting fields follows the order
* of fieldsSortable array returned by the schema.
*
* (todo?: currently there is no support for an arbitrary ordering of sorting
* fields, querySortToDjango could be altered to support that behaviour)
*
* To install this plugin:
* 1) include this file in your website,
* 2) make sure it's after tenclouds.crud.js.models.js,
* 3) make sure multi_field_ordering of you collection is set to true.
*/

// save the original methods
var orig_collection = crud.collection.Collection;

/**
* Use multi_field_ordering boolean parameter to enable multi-field ordering
* for your collection.
*/
crud.collection.Collection = crud.collection.Collection.extend({

    /**
    * Enables multi field ordering.
    */
    multi_field_ordering: false,

    /**
    * Defines the order in which ordering fields are toggled.
    *
    * Available states: undefined, 'up' and 'down'.
    */
    sortToggleOrder: [undefined, 'up', 'down'],

    /**
    * Makes this.querySort mapping available just after fetch.
    */
    parse: function (resp) {
        if (!this.multi_field_ordering)
            return orig_collection.prototype.parse.call(this, resp);
        var orig = orig_collection.prototype.parse.call(this, resp);
        // populate querySort
        this.querySort = this.makeOrderingDict();
        return orig;
    },

    /**
    * Creates a map of all available ordering options to their state.
    * The states will be one of the following: 'up', 'down' or undefined.
    * Uses this.fieldsSortable (meta) and this.ordering (collection).
    * @returns The mapping.
    */
    makeOrderingDict: function(){
        if (!this.multi_field_ordering)
            return orig_collection.prototype.makeOrderingDict.call(this);
        var order_mapping = {};
        var that = this;
        // adds all sorting fields, inactive by default
        _.each(this.fieldsSortable, function(orderer){
            order_mapping[orderer] = undefined;
        });
        // adds current active fields
        _.each(this.ordering, function(orderer){
            var is_reverse = orderer.indexOf('-') === 0;
            var direction = is_reverse ? "down" : "up";
            orderer = is_reverse ? orderer.substring(1) : orderer;
            order_mapping[orderer] = direction;
        });
        return order_mapping;
    },

    /**
    * Updates sorting order data for the give sortField.
    * @argument sortField Field to change the ordering for.
    * @returns State of the sorter after change.
    */
    querySortOrder: function (sortField) {
        if (!this.multi_field_ordering)
            return orig_collection.prototype.querySortOrder.call(this, sortField);
        var orderToSet;
        if (!orderToSet) {
            var ci = _.indexOf(this.sortToggleOrder, this.querySort[sortField]);

            // ensure there is at least one active field at a time
            var states = this.sortToggleOrder;
            // get all active filters
            var active = _.compact(_.values(this.querySort));
            // check if we are altering the active filter and it's only active
            if (active.length === 1 && this.querySort[sortField] !== undefined) {
                // if so, remove currect and undefined states
                states = _.without(this.sortToggleOrder,
                    this.querySort[sortField], undefined);
            }
            // can't change, return
            if (states.length === 0) return;

            orderToSet = states[(ci + 1) % states.length];
        }
        this.querySort[sortField] = orderToSet;
    }

});

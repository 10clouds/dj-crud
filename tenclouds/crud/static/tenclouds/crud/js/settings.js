/**
* Configuration module for CRUD.
*
* The purpose of this file is to expose general module settings. To alter the
* behaviour, simply assign any of the known settings, for example:
*
*   crud.settings.static_url = '/static'
*/
crud.settings = {

    /**
    * The url to prepend to any static file requests.
    * It is used for template fetching. TODO: check it this should be applied
    * somewhere else too.
    */
    static_url: '/static',

    /**
    * Ejs template path, tied to the app/static folder structure.
    * Combined with static_url forms the complete url to an ejs template:
    *
    *    <static_url>/<template_dir>/<template_name>.ejs
    *
    * Override crud.template.template_function to change this behaviour.
    */
    template_path: 'tenclouds/crud/ejs'

};

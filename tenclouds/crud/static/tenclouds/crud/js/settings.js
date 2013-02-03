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
    * Currently it is used only for template fetching. TODO: check it this
    * should be applied somewhere else too.
    */
    static_url: '/static',

    /**
    * Ejs template path, tied to the app/static folder structure.
    * Used by ``crud.crud_template`` - template getter for builtin templates.
    * Combined with static_url forms the complete url to an ejs template:
    *
    *    <static_url>/<template_path>/<template_name>.ejs
    *
    * Please note that this is different from the crud.template function, which
    * ommits this setting and simply returns returns:
    *
    *   <static_url>/<template_name>
    *
    */
    template_path: 'tenclouds/crud/ejs',

    preloader: false,
    preloader_img: null

};

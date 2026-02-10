odoo.define('kpi_form.competency_hierarchy', function (require) {
    "use strict";

    // Import required modules
    var ListRenderer = require('web.ListRenderer');
    var ListController = require('web.ListController');
    var ListView = require('web.ListView');
    var core = require('web.core');
    var _t = core._t;

    // Extend ListRenderer to add hierarchy styling
    ListRenderer.include({
        _renderRow: function (record) {
            var $tr = this._super.apply(this, arguments);

            // Add data attributes for CSS styling
            var level = record.data.level || 1;
            var hasChildren = false;

            // Check if line has children
            if (record.data.child_ids && record.data.child_ids.res_ids) {
                hasChildren = record.data.child_ids.res_ids.length > 0;
            }

            $tr.attr('data-level', level);
            $tr.attr('data-has-children', hasChildren);

            return $tr;
        },

        _renderBody: function () {
            var $body = this._super.apply(this, arguments);

            // Add CSS class to the entire list
            $body.addClass('competency-hierarchy-list');

            return $body;
        }
    });

    // Optional: Extend ListController for custom actions
    ListController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);

            // Add custom button to the list view
            if (this.$buttons) {
                var $reorderButton = $('<button>', {
                    type: 'button',
                    class: 'btn btn-secondary o_reorder_competencies',
                    html: '<i class="fa fa-sort"></i> ' + _t('Reorder')
                });

                $reorderButton.on('click', this._onReorderCompetencies.bind(this));
                this.$buttons.find('.o_list_buttons').prepend($reorderButton);
            }
        },

        _onReorderCompetencies: function () {
            // Custom reorder logic
            this.do_action({
                type: 'ir.actions.client',
                tag: 'display_notification',
                params: {
                    title: _t('Reorder'),
                    message: _t('Competencies reordered successfully.'),
                    type: 'info',
                    sticky: false,
                }
            });
        }
    });

    // Register the patch
    return {
        ListRenderer: ListRenderer,
        ListController: ListController
    };
});
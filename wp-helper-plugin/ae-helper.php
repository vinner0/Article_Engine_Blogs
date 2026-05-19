<?php
/**
 * Plugin Name: Article Engine Helper
 * Description: Registers ae_content_uid (REST) + /ae/v1/find idempotency route; optional /ae/v1/meta for blocked SEO meta.
 * Version: 1.0.0
 * Requires PHP: 7.4
 */
if (!defined('ABSPATH')) exit;

add_action('init', function () {
    register_post_meta('post', 'ae_content_uid', [
        'show_in_rest'      => true,
        'single'            => true,
        'type'              => 'string',
        'auth_callback'     => function () { return current_user_can('edit_posts'); },
    ]);
});

add_action('rest_api_init', function () {
    register_rest_route('ae/v1', '/find', [
        'methods'  => 'GET',
        'permission_callback' => function () { return current_user_can('edit_posts'); },
        'callback' => function (WP_REST_Request $r) {
            $uid = sanitize_text_field($r->get_param('uid'));
            $q = new WP_Query([
                'post_type'   => 'post',
                'post_status' => 'any',
                'meta_key'    => 'ae_content_uid',
                'meta_value'  => $uid,
                'fields'      => 'ids',
                'posts_per_page' => 1,
            ]);
            if (empty($q->posts)) {
                return new WP_Error('ae_not_found', 'no post for uid', ['status' => 404]);
            }
            return ['id' => (int) $q->posts[0]];
        },
    ]);
    register_rest_route('ae/v1', '/meta/(?P<id>\d+)', [
        'methods'  => 'POST',
        'permission_callback' => function () { return current_user_can('edit_posts'); },
        'callback' => function (WP_REST_Request $r) {
            $id = (int) $r['id'];
            if (get_post_status($id) === false) {
                return new WP_Error('ae_bad', 'bad id', ['status' => 400]);
            }
            foreach (($r->get_json_params()['meta'] ?? []) as $k => $v) {
                update_post_meta($id, sanitize_key($k), wp_kses_post($v));
            }
            return ['ok' => true, 'id' => $id];
        },
    ]);
});

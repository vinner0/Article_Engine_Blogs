<?php
/**
 * Plugin Name: Article Engine Helper
 * Description: Registers ae_content_uid (REST) + /ae/v1/find idempotency route; optional /ae/v1/meta for blocked SEO meta; in-article course box.
 * Version: 1.1.0
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
                // SEO meta (rank_math_title, _yoast_wpseo_metadesc, ...) is PLAIN
                // TEXT; the SEO plugin re-encodes on output. wp_kses_post would
                // entity-encode '&' -> '&amp;' causing double-encoded <title>/
                // <meta> (N6). sanitize_text_field strips tags w/o entity-encoding.
                update_post_meta($id, sanitize_key($k), sanitize_text_field($v));
            }
            return ['ok' => true, 'id' => $id];
        },
    ]);
});

// ─── In-article course box (1.1.0) ───────────────────────────────────────────
// Post meta `ae_course` = course id; option `ae_course_boxes` = {id: {name,pitch,funding,cta,url}}.
// Both written by scripts/course_box.py. Posts without ae_course are untouched.

add_action('rest_api_init', function () {
    register_rest_route('ae/v1', '/course-boxes', [
        'methods'  => 'POST',
        'permission_callback' => function () { return current_user_can('manage_options'); },
        'callback' => function (WP_REST_Request $r) {
            $clean = [];
            foreach (($r->get_json_params()['boxes'] ?? []) as $id => $b) {
                $clean[sanitize_key($id)] = [
                    'name'    => sanitize_text_field($b['name'] ?? ''),
                    'pitch'   => sanitize_text_field($b['pitch'] ?? ''),
                    'funding' => sanitize_text_field($b['funding'] ?? ''),
                    'cta'     => sanitize_text_field($b['cta'] ?? ''),
                    'url'     => esc_url_raw($b['url'] ?? ''),
                ];
            }
            update_option('ae_course_boxes', $clean, false);
            return ['ok' => true, 'count' => count($clean)];
        },
    ]);
});

function ae_course_box_for_post($post_id) {
    $id = get_post_meta($post_id, 'ae_course', true);
    $boxes = get_option('ae_course_boxes', []);
    return ($id && !empty($boxes[$id]['url'])) ? [$id, $boxes[$id]] : null;
}

function ae_course_box_html($id, $b, $placement) {
    $attrs = sprintf('data-ae-course="%s" data-ae-placement="%s"', esc_attr($id), esc_attr($placement));
    if ($placement === 'inline') {
        return sprintf('<aside class="ae-cbox ae-cbox--inline" %s><span class="ae-cbox__lead">Learn this hands-on:</span> '
            . '<a href="%s">%s</a> <span class="ae-cbox__fund">%s</span></aside>',
            $attrs, esc_url($b['url']), esc_html($b['name']), esc_html($b['funding']));
    }
    return sprintf('<aside class="ae-cbox ae-cbox--full" %s><p class="ae-cbox__kicker">Want to learn this properly?</p>'
        . '<p class="ae-cbox__name">%s</p><p class="ae-cbox__pitch">%s</p><p class="ae-cbox__fund">%s</p>'
        . '<a class="ae-cbox__btn" href="%s">%s &rarr;</a></aside>',
        $attrs, esc_html($b['name']), esc_html($b['pitch']), esc_html($b['funding']),
        esc_url($b['url']), esc_html($b['cta']));
}

add_filter('the_content', function ($content) {
    if (!is_singular('post') || !in_the_loop() || !is_main_query()) return $content;
    $hit = ae_course_box_for_post(get_the_ID());
    if (!$hit) return $content;
    list($id, $b) = $hit;
    // Compact box just before the 3rd <h2> (i.e. after the 2nd section); skipped on short posts.
    if (preg_match_all('/<h2[\s>]/i', $content, $m, PREG_OFFSET_CAPTURE) && count($m[0]) >= 3) {
        $pos = $m[0][2][1];
        $content = substr($content, 0, $pos) . ae_course_box_html($id, $b, 'inline') . substr($content, $pos);
    }
    return $content . ae_course_box_html($id, $b, 'end');
}, 20);

add_action('wp_head', function () {
    if (!is_singular('post') || !ae_course_box_for_post(get_queried_object_id())) return;
    echo '<style id="ae-cbox-css">'
        . '.ae-cbox{border:1px solid #d9e2ec;border-left:4px solid #0b6bcb;background:#f5f9fd;border-radius:6px;margin:1.6em 0;color:#1f2933}'
        . '.ae-cbox--inline{padding:.8em 1em;font-size:.97em;line-height:1.5}'
        . '.ae-cbox--inline a{font-weight:600}'
        . '.ae-cbox--inline .ae-cbox__fund{display:block;font-size:.88em;color:#52606d;margin-top:.2em}'
        . '.ae-cbox--full{padding:1.3em 1.4em}'
        . '.ae-cbox--full p{margin:0 0 .45em}'
        . '.ae-cbox__kicker{font-size:.8em;text-transform:uppercase;letter-spacing:.06em;color:#0b6bcb;font-weight:700}'
        . '.ae-cbox__name{font-size:1.2em;font-weight:700;line-height:1.3}'
        . '.ae-cbox__fund{font-size:.9em;color:#52606d}'
        . '.ae-cbox__btn{display:inline-block;margin-top:.5em;padding:.65em 1.2em;background:#0b6bcb;color:#fff!important;'
        . 'border-radius:5px;font-weight:600;text-decoration:none!important}'
        . '.ae-cbox__btn:hover{background:#0a58a8}'
        . '</style>';
});

add_action('wp_footer', function () {
    if (!is_singular('post') || !ae_course_box_for_post(get_queried_object_id())) return;
    $slug = esc_js(get_post_field('post_name', get_queried_object_id()));
    echo "<script>document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('.ae-cbox a');"
        . "if(!a)return;var box=a.closest('.ae-cbox');var p={course:box.dataset.aeCourse,placement:box.dataset.aePlacement,article:'$slug'};"
        . "if(typeof gtag==='function'){gtag('event','ae_course_box_click',p);}"
        . "else{(window.dataLayer=window.dataLayer||[]).push(Object.assign({event:'ae_course_box_click'},p));}});</script>";
});

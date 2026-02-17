<?php
/**
 * MPS Support Chatbot Widget - WordPress Integration
 * 
 * Add this code to your theme's functions.php file or create a custom plugin
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

class MPS_Chatbot_Widget {
    
    private $options;
    
    public function __construct() {
        add_action('init', array($this, 'init'));
        add_action('wp_footer', array($this, 'render_widget'));
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('admin_init', array($this, 'settings_init'));
    }
    
    public function init() {
        // Load default options
        $this->options = get_option('mps_chatbot_options', array(
            'enabled' => true,
            'api_base_url' => 'https://your-api.com',
            'show_to_logged_in' => true,
            'show_to_guests' => true,
            'exclude_pages' => '',
            'primary_color' => '#2563eb',
            'position_bottom' => '20px',
            'position_right' => '20px'
        ));
    }
    
    public function render_widget() {
        // Check if widget should be displayed
        if (!$this->should_display_widget()) {
            return;
        }
        
        // Get current user info
        $current_user = wp_get_current_user();
        $user_name = $current_user->exists() ? $current_user->display_name : 'Visitor';
        
        // Prepare configuration
        $config = array(
            'apiBaseUrl' => $this->options['api_base_url'],
            'userName' => $user_name,
            'theme' => array(
                'primaryColor' => $this->options['primary_color']
            ),
            'position' => array(
                'bottom' => $this->options['position_bottom'],
                'right' => $this->options['position_right']
            ),
            'initialMessage' => true
        );
        
        ?>
        <!-- MPS Support Chatbot Widget -->
        <script>
        (function() {
            // Load the widget script
            var script = document.createElement('script');
            script.src = '<?php echo esc_url($this->options['api_base_url']); ?>/widget/chatbot-widget.umd.js';
            script.onload = function() {
                if (window.ChatbotWidget) {
                    window.ChatbotWidget.init(<?php echo json_encode($config); ?>);
                    console.log('✅ MPS Support Chatbot loaded for WordPress');
                }
            };
            script.onerror = function() {
                console.error('❌ Failed to load MPS Support Chatbot');
            };
            document.head.appendChild(script);
        })();
        </script>
        <?php
    }
    
    private function should_display_widget() {
        // Check if widget is enabled
        if (!$this->options['enabled']) {
            return false;
        }
        
        // Check user authentication requirements
        if (!$this->options['show_to_logged_in'] && is_user_logged_in()) {
            return false;
        }
        
        if (!$this->options['show_to_guests'] && !is_user_logged_in()) {
            return false;
        }
        
        // Check excluded pages
        if (!empty($this->options['exclude_pages'])) {
            $excluded_pages = array_map('trim', explode(',', $this->options['exclude_pages']));
            $current_page_id = get_the_ID();
            
            if (in_array($current_page_id, $excluded_pages)) {
                return false;
            }
        }
        
        // Don't show on admin pages
        if (is_admin()) {
            return false;
        }
        
        return true;
    }
    
    public function add_admin_menu() {
        add_options_page(
            'MPS Chatbot Settings',
            'MPS Chatbot',
            'manage_options',
            'mps-chatbot',
            array($this, 'options_page')
        );
    }
    
    public function settings_init() {
        register_setting('mps_chatbot', 'mps_chatbot_options');
        
        add_settings_section(
            'mps_chatbot_section',
            'Chatbot Configuration',
            array($this, 'settings_section_callback'),
            'mps_chatbot'
        );
        
        // Add settings fields
        $fields = array(
            'enabled' => 'Enable Chatbot',
            'api_base_url' => 'API Base URL',
            'show_to_logged_in' => 'Show to Logged-in Users',
            'show_to_guests' => 'Show to Guests',
            'exclude_pages' => 'Exclude Pages (comma-separated IDs)',
            'primary_color' => 'Primary Color',
            'position_bottom' => 'Position from Bottom',
            'position_right' => 'Position from Right'
        );
        
        foreach ($fields as $field => $label) {
            add_settings_field(
                $field,
                $label,
                array($this, 'field_callback'),
                'mps_chatbot',
                'mps_chatbot_section',
                array('field' => $field)
            );
        }
    }
    
    public function settings_section_callback() {
        echo '<p>Configure the MPS Support Chatbot widget settings.</p>';
    }
    
    public function field_callback($args) {
        $field = $args['field'];
        $value = isset($this->options[$field]) ? $this->options[$field] : '';
        
        switch ($field) {
            case 'enabled':
            case 'show_to_logged_in':
            case 'show_to_guests':
                echo '<input type="checkbox" name="mps_chatbot_options[' . $field . ']" value="1" ' . checked(1, $value, false) . ' />';
                break;
                
            case 'primary_color':
                echo '<input type="color" name="mps_chatbot_options[' . $field . ']" value="' . esc_attr($value) . '" />';
                break;
                
            case 'exclude_pages':
                echo '<textarea name="mps_chatbot_options[' . $field . ']" rows="3" cols="50">' . esc_textarea($value) . '</textarea>';
                echo '<p class="description">Enter page IDs separated by commas (e.g., 123, 456, 789)</p>';
                break;
                
            default:
                echo '<input type="text" name="mps_chatbot_options[' . $field . ']" value="' . esc_attr($value) . '" class="regular-text" />';
                break;
        }
    }
    
    public function options_page() {
        ?>
        <div class="wrap">
            <h1>MPS Support Chatbot Settings</h1>
            
            <div class="notice notice-info">
                <p><strong>MPS Support Chatbot</strong> provides AI-powered customer support with automatic escalation to Salesforce.</p>
            </div>
            
            <form action="options.php" method="post">
                <?php
                settings_fields('mps_chatbot');
                do_settings_sections('mps_chatbot');
                submit_button();
                ?>
            </form>
            
            <div class="card">
                <h2>Widget Preview</h2>
                <p>The chatbot widget will appear as a floating button in the bottom-right corner of your website.</p>
                <p><strong>Features:</strong></p>
                <ul>
                    <li>✅ Deterministic responses based on knowledge base</li>
                    <li>✅ Automatic escalation to Salesforce for unhandled queries</li>
                    <li>✅ Professional UI that matches your website design</li>
                    <li>✅ Mobile responsive and accessible</li>
                    <li>✅ No interference with existing website functionality</li>
                </ul>
            </div>
            
            <div class="card">
                <h2>Troubleshooting</h2>
                <p>If the chatbot is not appearing:</p>
                <ol>
                    <li>Ensure the "Enable Chatbot" option is checked</li>
                    <li>Verify the API Base URL is correct and accessible</li>
                    <li>Check that the current page is not in the excluded pages list</li>
                    <li>Check browser console for JavaScript errors</li>
                </ol>
            </div>
        </div>
        
        <style>
        .card {
            background: #fff;
            border: 1px solid #ccd0d4;
            border-radius: 4px;
            padding: 20px;
            margin-top: 20px;
        }
        .card h2 {
            margin-top: 0;
        }
        </style>
        <?php
    }
}

// Initialize the plugin
new MPS_Chatbot_Widget();

/**
 * Shortcode for manual widget placement
 * Usage: [mps_chatbot]
 */
function mps_chatbot_shortcode($atts) {
    $atts = shortcode_atts(array(
        'api_url' => 'https://your-api.com',
        'user_name' => '',
        'primary_color' => '#2563eb'
    ), $atts);
    
    $current_user = wp_get_current_user();
    $user_name = !empty($atts['user_name']) ? $atts['user_name'] : 
                 ($current_user->exists() ? $current_user->display_name : 'Visitor');
    
    $config = array(
        'apiBaseUrl' => $atts['api_url'],
        'userName' => $user_name,
        'theme' => array(
            'primaryColor' => $atts['primary_color']
        ),
        'initialMessage' => true
    );
    
    ob_start();
    ?>
    <div id="mps-chatbot-shortcode"></div>
    <script>
    (function() {
        var script = document.createElement('script');
        script.src = '<?php echo esc_url($atts['api_url']); ?>/widget/chatbot-widget.umd.js';
        script.onload = function() {
            if (window.ChatbotWidget) {
                window.ChatbotWidget.init(<?php echo json_encode($config); ?>);
            }
        };
        document.head.appendChild(script);
    })();
    </script>
    <?php
    return ob_get_clean();
}
add_shortcode('mps_chatbot', 'mps_chatbot_shortcode');

/**
 * Add chatbot status to WordPress admin bar
 */
function mps_chatbot_admin_bar($wp_admin_bar) {
    if (!current_user_can('manage_options')) {
        return;
    }
    
    $options = get_option('mps_chatbot_options', array('enabled' => false));
    $status = $options['enabled'] ? 'Enabled' : 'Disabled';
    $class = $options['enabled'] ? 'mps-chatbot-enabled' : 'mps-chatbot-disabled';
    
    $wp_admin_bar->add_node(array(
        'id' => 'mps-chatbot-status',
        'title' => '🤖 Chatbot: ' . $status,
        'href' => admin_url('options-general.php?page=mps-chatbot'),
        'meta' => array('class' => $class)
    ));
}
add_action('admin_bar_menu', 'mps_chatbot_admin_bar', 100);

/**
 * Add admin bar styles
 */
function mps_chatbot_admin_bar_styles() {
    ?>
    <style>
    .mps-chatbot-enabled { color: #46b450 !important; }
    .mps-chatbot-disabled { color: #dc3232 !important; }
    </style>
    <?php
}
add_action('wp_head', 'mps_chatbot_admin_bar_styles');
add_action('admin_head', 'mps_chatbot_admin_bar_styles');
?>
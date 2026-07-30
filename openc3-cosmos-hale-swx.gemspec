# encoding: ascii-8bit

# Create the overall gemspec
Gem::Specification.new do |s|
  s.name = 'openc3-cosmos-hale-swx'
  s.summary = 'Hale Space Weather Forecast'
  s.description = <<-EOF
    Hale Space Weather Forecast Plugin
  EOF
  s.license = 'OpenC3'
  s.authors = ['Clay Ito']
  s.email = ['clay@openc3.com']
  s.homepage = 'https://github.com/OpenC3/openc3-cosmos-hale-swx'
  s.version = "1.0.0"
  s.platform = Gem::Platform::RUBY

  s.metadata = {
    "source_code_uri" => "https://github.com/OpenC3/openc3-cosmos-hale-swx",
    "openc3_cosmos_minimum_version" => "6.0.0",
    "openc3_store_access_type" => "public",
    "openc3_store_keywords" => "Space Weather, Hale, Forecast, API",
    "openc3_store_image" => "public/store_img.png",
  }

  if ENV['VERSION']
    s.version = ENV['VERSION'].dup
  else
    time = Time.now.strftime("%Y%m%d%H%M%S")
    s.version = '0.0.0' + ".#{time}"
  end

  s.files = Dir.glob("{targets,lib,public,tools,microservices}/**/*") + %w(Rakefile README.md LICENSE.md plugin.txt)
end
